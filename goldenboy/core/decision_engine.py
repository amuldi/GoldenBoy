"""DecisionEngine: combines usage, task understanding, and progress into one
explained recommendation (a `GoldenBoyDecision`).

This is the layer the rest of the system (CLI `analyze`, future SDKs) talks
to. It does not replace `RiskEngine` -- `RiskEngine.assess()` is unchanged
and still the single source of truth for SAFE/CAUTION/LIMITED/CRITICAL, and
its existing, tested STALE-downgrade contract is untouched here. DecisionEngine
adds two things on top, deliberately kept out of RiskEngine itself so that
class's existing behavior/tests never change:

1. Task understanding: what kind of work this is (`TaskClassifier`) and how
   complex it looks (`Estimator`'s `complexity_score`, from
   `goldenboy.core.complexity` -- a real, independent signal derived from
   the task text itself, which `Estimator.estimate_task()` also feeds into
   its own cost formula. Earlier versions of this module back-computed
   complexity from the cost percentage instead; that stopped being
   necessary once complexity became the input to cost rather than the
   other way around -- see CHANGELOG.md).
2. A conservative confidence policy for budgets with UNKNOWN confidence
   (real adapters before their first `refresh_usage()` call, or any custom
   adapter that never sets `Budget.confidence`): an otherwise-SAFE verdict
   is treated as CAUTION, the same way RiskEngine already treats STALE, but
   as an explicit, separate, opt-in rule here -- RiskEngine's own UNKNOWN
   handling (and the test that pins it, `test_unknown_confidence_is_
   unaffected_by_the_stale_rule`) is intentionally left alone, since other
   callers (e.g. `MockProvider`, which always reports EXACT) may depend on
   that neutral default. This is "usage unavailable -> lower confidence ->
   conservative decision policy" applied specifically where the decision is
   actually made, not baked into a lower layer other callers share.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.estimator import Estimator, TaskEstimate
from goldenboy.core.risk import ExecutionMode, RiskEngine
from goldenboy.core.task_classifier import TaskClassification, TaskClassifier
from goldenboy.core.task_types import DecisionAction
from goldenboy.protocol import GoldenBoyDecision, RiskAssessment, TaskProfile, UsageSnapshot

# Complexity-label thresholds against `TaskEstimate.complexity_score`
# (0.0-1.0, see `goldenboy.core.complexity`). Fixed, documented constants
# (consistent with Estimator's own _MAX_SCAN_FILES-style constants) rather
# than a new GoldenBoyConfig field: this is a display bucketing of an
# existing measured signal, not an independent policy threshold that
# changes what Golden Boy actually does.
_COMPLEXITY_LOW_MAX = 0.25
_COMPLEXITY_MEDIUM_MAX = 0.50
_COMPLEXITY_HIGH_MAX = 0.75

# Below this combined confidence, DecisionEngine refuses to recommend an
# action other than ASK_USER (except under CRITICAL, where stopping/
# finishing safely takes priority over asking a question). Documented,
# fixed threshold -- see `_combined_confidence` for exactly what feeds it.
_ASK_USER_CONFIDENCE_THRESHOLD = 0.35

# Progress (0.0-1.0, caller-supplied) at or above which "only verification/
# cleanup remains" becomes the operative framing for SAFE/CAUTION/LIMITED.
_NEAR_DONE_PROGRESS = 0.85
# Progress at or above which CRITICAL still finishes essential work rather
# than stopping outright -- there's enough done that finishing is safer
# than abandoning it mid-unit.
_CRITICAL_FINISH_PROGRESS = 0.5

# Budget.confidence -> a weight in the decision-confidence blend. Documented
# here so the formula in `_combined_confidence` is auditable, not a black box.
_BUDGET_CONFIDENCE_WEIGHT = {
    UsageConfidence.EXACT: 1.0,
    UsageConfidence.ESTIMATED: 0.8,
    UsageConfidence.STALE: 0.4,
    UsageConfidence.UNKNOWN: 0.5,
}


def _complexity_label(complexity_score: float) -> str:
    if complexity_score < _COMPLEXITY_LOW_MAX:
        return "LOW"
    if complexity_score < _COMPLEXITY_MEDIUM_MAX:
        return "MEDIUM"
    if complexity_score < _COMPLEXITY_HIGH_MAX:
        return "HIGH"
    return "VERY_HIGH"



# Applied as a multiplier on the blended confidence when the classifier
# found no keyword match at all (TaskType.UNKNOWN, confidence 0.0): not
# knowing what kind of work this even is should pull overall confidence
# down more than a simple three-way mean would on its own, since the other
# two signals (cost estimate, budget reading) say nothing about whether
# the *task itself* was understood.
_UNCLASSIFIED_TASK_CONFIDENCE_GATE = 0.5


def _combined_confidence(
    task_estimate: TaskEstimate, classification: TaskClassification, budget: Budget
) -> float:
    """Documented blend of three independent confidence signals -- not a
    learned weighting, so it's auditable by reading this function. Each
    term is already itself honestly labeled (Estimator's own confidence,
    the classifier's heuristic match-strength, and a fixed per-
    UsageConfidence weight); an unclassified task additionally applies
    `_UNCLASSIFIED_TASK_CONFIDENCE_GATE` (see its docstring)."""
    budget_weight = _BUDGET_CONFIDENCE_WEIGHT.get(budget.confidence, 0.5)
    mean = (task_estimate.confidence + classification.confidence + budget_weight) / 3.0
    gate = _UNCLASSIFIED_TASK_CONFIDENCE_GATE if classification.confidence == 0.0 else 1.0
    return round(mean * gate, 3)


def _risk_reason_code(
    budget: Budget, estimate: TaskEstimate, config: GoldenBoyConfig, raw_mode: ExecutionMode
) -> str:
    """Re-derives *which* branch of RiskEngine.assess() produced `raw_mode`,
    for the protocol's human/machine-readable `reason_code` -- read-only
    introspection of the same inputs, not a reimplementation of the
    decision (RiskEngine.assess() is still what's actually called)."""
    if budget.is_exhausted():
        return "BUDGET_AT_OR_BELOW_SAFETY_MARGIN"
    usable = budget.usable_percentage
    required = estimate.estimated_percentage
    if required > usable:
        return "ESTIMATED_COST_EXCEEDS_USABLE_BUDGET"
    ratio = required / usable if usable > 0 else 1.0
    if ratio >= config.caution_ratio:
        return "COST_TO_BUDGET_RATIO_AT_OR_ABOVE_CAUTION_THRESHOLD"
    return "COST_TO_BUDGET_RATIO_BELOW_CAUTION_THRESHOLD"


def _decide_action(
    mode: ExecutionMode, progress: Optional[float], confidence: float
) -> Tuple[DecisionAction, List[str]]:
    """The decision table: (effective risk mode, progress) -> (action,
    ordered recommendation). Progress is caller-supplied and optional --
    Golden Boy does not observe an agent's edits itself, so `None` means
    "unknown," handled as "treat as just starting" rather than guessed."""
    known_progress = progress if progress is not None else 0.0
    near_done = known_progress >= _NEAR_DONE_PROGRESS

    if confidence < _ASK_USER_CONFIDENCE_THRESHOLD and mode != ExecutionMode.CRITICAL:
        return DecisionAction.ASK_USER, [
            "Confidence in this recommendation is too low to act on automatically.",
            "Share more detail about the task, or confirm remaining budget/progress explicitly.",
        ]

    if mode == ExecutionMode.CRITICAL:
        if known_progress >= _CRITICAL_FINISH_PROGRESS:
            return DecisionAction.FINISH, [
                "Finish the essential remaining implementation.",
                "Run only the tests/checks that verify it.",
                "Stop and checkpoint anything else.",
            ]
        return DecisionAction.STOP, [
            "Checkpoint current progress now.",
            "Do not start further work until budget is refreshed.",
        ]

    if near_done:
        return DecisionAction.VERIFY, [
            "Implementation appears close to complete.",
            "Run verification (tests/lint/build) rather than adding new scope.",
            "Stop once verification passes.",
        ]

    if mode == ExecutionMode.LIMITED:
        return DecisionAction.REDUCE_SCOPE, [
            "Constrain remaining work to P0/P1 items.",
            "Explicitly defer P2-P4 items and say so.",
        ]

    if mode == ExecutionMode.CAUTION:
        return DecisionAction.CONTINUE, [
            "Continue, but avoid opening new scope beyond the current task.",
            "Re-check budget before starting any additional unit of work.",
        ]

    # SAFE
    if progress is None or known_progress == 0.0:
        return DecisionAction.RUN, ["Proceed with the task as scoped."]
    return DecisionAction.CONTINUE, ["Continue with the task as scoped."]


def _reason_text(
    task_type: str,
    complexity_label: str,
    budget: Budget,
    estimate: TaskEstimate,
    mode: ExecutionMode,
    effective_mode: ExecutionMode,
    action: DecisionAction,
    progress: Optional[float],
) -> str:
    """Builds the human-readable explanation from the actual numbers just
    computed -- every clause below reads a real value passed in; nothing is
    invented or templated with placeholder text."""
    parts = [
        f"Task classified as {task_type} ({complexity_label} complexity, "
        f"estimated cost {estimate.estimated_percentage:.1f}% of budget, "
        f"confidence {estimate.confidence:.2f}).",
        f"Remaining budget is {budget.remaining_percentage:.1f}% "
        f"({budget.confidence.value.lower()} via {budget.source}).",
    ]
    if effective_mode != mode:
        parts.append(
            f"Risk mode {mode.value} was treated as {effective_mode.value} because usage "
            "confidence is UNKNOWN (no real reading has been taken yet)."
        )
    else:
        parts.append(f"Risk mode: {effective_mode.value}.")
    if progress is not None:
        parts.append(f"Reported progress: {progress * 100:.0f}%.")
    parts.append(f"Recommended action: {action.value.upper()}.")
    return " ".join(parts)


@dataclass
class DecisionEngine:
    """Ties `Estimator`, `TaskClassifier`, and `RiskEngine` together into one
    explained `GoldenBoyDecision`. Stateless aside from its config; safe to
    construct per call."""

    config: Optional[GoldenBoyConfig] = None

    def __post_init__(self) -> None:
        self._config = self.config or get_default_config()
        self._estimator = Estimator(config=self._config)
        self._classifier = TaskClassifier()
        self._risk_engine = RiskEngine(config=self._config)

    def decide(
        self,
        task: str,
        provider: ProviderAdapter,
        progress: Optional[float] = None,
    ) -> GoldenBoyDecision:
        """Produce one `GoldenBoyDecision` for `task` against `provider`'s
        current budget. `progress` (0.0-1.0) is optional and caller-supplied
        -- Golden Boy has no way to observe how much of the task is actually
        done on its own; omit it (or pass None) if genuinely unknown rather
        than guessing."""
        if progress is not None and not (0.0 <= progress <= 1.0):
            raise ValueError(f"progress must be within [0.0, 1.0], got {progress!r}")

        budget = provider.get_available_budget()
        estimate = self._estimator.estimate_task(task)
        classification = self._classifier.classify(task)
        raw_mode = self._risk_engine.assess(budget, estimate)

        effective_mode = raw_mode
        if raw_mode == ExecutionMode.SAFE and budget.confidence == UsageConfidence.UNKNOWN:
            effective_mode = ExecutionMode.CAUTION

        confidence = _combined_confidence(estimate, classification, budget)
        action, recommendation = _decide_action(effective_mode, progress, confidence)

        complexity = estimate.complexity_score
        complexity_label = _complexity_label(complexity)

        reason = _reason_text(
            classification.task_type.value, complexity_label, budget, estimate,
            raw_mode, effective_mode, action, progress,
        )

        task_profile = TaskProfile(
            task_type=classification.task_type.value,
            task_type_confidence=classification.confidence,
            complexity=complexity,
            complexity_label=complexity_label,
            estimated_cost_percentage=estimate.estimated_percentage,
            estimated_cost_confidence=estimate.confidence,
            signals=classification.signals,
            complexity_signals=estimate.complexity_signals,
            secondary_task_types=[t.value for t in classification.secondary_task_types],
        )
        usage_snapshot = UsageSnapshot(
            remaining_percentage=budget.remaining_percentage,
            usable_percentage=budget.usable_percentage,
            source=budget.source,
            confidence=budget.confidence.value,
        )
        reason_code = _risk_reason_code(budget, estimate, self._config, raw_mode)
        if effective_mode != raw_mode:
            reason_code += "_THEN_UNKNOWN_CONFIDENCE_DOWNGRADE"
        risk_assessment = RiskAssessment(
            mode=effective_mode.value,
            reason_code=reason_code,
            ratio=(estimate.estimated_percentage / budget.usable_percentage)
            if budget.usable_percentage > 0
            else None,
        )

        return GoldenBoyDecision.build(
            task=task_profile,
            usage=usage_snapshot,
            risk=risk_assessment,
            action=action.value,
            confidence=confidence,
            reason=reason,
            recommendation=recommendation,
        )

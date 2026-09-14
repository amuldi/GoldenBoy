"""Historical replay / backtesting: "would a different resource-allocation
policy have made better decisions on these actual past tasks?"

This is an *AI agent resource-allocation* backtest, not a financial one
(see the project brief). It only ever operates on real `TaskEvent`s (from
`HistoryStore`, or an explicit JSONL export) -- there is no bundled or
synthetic dataset. With zero or few events (see `_MIN_EVENTS_FOR_METRICS`),
`run_backtest` reports every metric as `None`/"N/A" rather than computing a
statistically meaningless percentage from a handful of rows.

Methodology and its limits (read before trusting a result):
    - Ground truth label per event: `outcome == "completed"` is "success",
      `"failed"`/`"deferred"` is "not success". A policy's PROCEED/STOP
      decision is compared against that same label -- this is standard
      off-policy evaluation from logged outcomes, and it carries the
      standard limitation of that method: an event's logged outcome
      reflects what happened under whatever decision Golden Boy *actually*
      made at the time, not under the alternate policy being scored. This
      is an approximation, not a causal counterfactual -- treat these
      numbers as a descriptive comparison on *this* logged data, not proof
      a policy would perform identically going forward.
    - `walk_forward_folds()` chronologically partitions events so a future
      *learned* policy (see `goldenboy.core.policies`' module docstring on
      why none exist yet) can be evaluated without training on its own
      test period. Today's policies are fixed-threshold/deterministic and
      don't fit anything, so folding does not change their scores -- it
      exists as tested, ready infrastructure for when a data-driven policy
      is added, not because it changes today's numbers.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from goldenboy.core.history import TaskEvent
from goldenboy.core.policies import Policy, PolicyDecision, PolicyInput, default_baseline_policies

# Below this many events, every ratio below is reported as None -- with,
# say, 3 data points a "67% completion rate" implies far more statistical
# weight than it has. Fixed, documented threshold.
_MIN_EVENTS_FOR_METRICS = 10

_SUCCESS_OUTCOME = "completed"


def _label(event: TaskEvent) -> bool:
    """True = the task actually completed; False otherwise (failed or
    deferred). The ground-truth target every policy is scored against."""
    return event.outcome == _SUCCESS_OUTCOME


def _to_policy_input(event: TaskEvent) -> PolicyInput:
    return PolicyInput(
        remaining_percentage=event.remaining_usage_start,
        estimated_cost_percentage=event.estimated_cost_percentage,
        usage_confidence=event.usage_confidence,
    )


@dataclass
class PolicyMetrics:
    policy_name: str
    n: int
    proceed_count: int
    stop_count: int
    precision: Optional[float]  # of PROCEED decisions, fraction that actually completed
    recall: Optional[float]  # of actually-completed tasks, fraction the policy would have let proceed
    accuracy: Optional[float]
    premature_stop_rate: Optional[float]  # fraction of ALL events: policy said STOP, task actually completed
    unnecessary_continuation_rate: Optional[float]  # fraction of ALL events: PROCEED, task did not complete


@dataclass
class BacktestReport:
    dataset_size: int
    policies: List[PolicyMetrics] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def render(self) -> str:
        if self.dataset_size < _MIN_EVENTS_FOR_METRICS:
            return (
                f"Backtest: {self.dataset_size} event(s) available "
                f"(need at least {_MIN_EVENTS_FOR_METRICS}).\n"
                "N/A — insufficient validated data."
            )
        header = (
            f"{'Policy':<28} {'Precision':>10} {'Recall':>10} {'Accuracy':>10} "
            f"{'PrematureStop':>14} {'UnnecessaryContinue':>20}"
        )
        lines = [f"Backtest over {self.dataset_size} historical event(s):", header, "-" * len(header)]

        def _fmt(v: Optional[float]) -> str:
            return f"{v * 100:.1f}%" if v is not None else "N/A"

        for m in self.policies:
            lines.append(
                f"{m.policy_name:<28} {_fmt(m.precision):>10} {_fmt(m.recall):>10} "
                f"{_fmt(m.accuracy):>10} {_fmt(m.premature_stop_rate):>14} "
                f"{_fmt(m.unnecessary_continuation_rate):>20}"
            )
        if self.limitations:
            lines.append("")
            lines.append("Limitations:")
            for note in self.limitations:
                lines.append(f"  - {note}")
        return "\n".join(lines)


_DEFAULT_LIMITATIONS = [
    "Off-policy evaluation from logged outcomes: an event's recorded outcome reflects the "
    "decision Golden Boy actually made at the time, not the alternate policy being scored here. "
    "This is a descriptive comparison on existing data, not a causal guarantee of future behavior.",
    "'deferred' and 'failed' outcomes are both scored as 'not completed' -- they are not "
    "distinguished as different failure modes in these metrics.",
    "Resource-waste (budget percentage points) is not reported: estimating it would require "
    "simulating what an alternate policy's own execution would have consumed, which this "
    "logged-outcome methodology cannot support without fabricating a number.",
]


def _score_policy(policy: Policy, events: List[TaskEvent]) -> PolicyMetrics:
    tp = fp = fn = tn = 0
    proceed_count = stop_count = 0

    for event in events:
        decision = policy.decide(_to_policy_input(event))
        actually_completed = _label(event)

        if decision == PolicyDecision.PROCEED:
            proceed_count += 1
            if actually_completed:
                tp += 1
            else:
                fp += 1
        else:
            stop_count += 1
            if actually_completed:
                fn += 1
            else:
                tn += 1

    n = len(events)
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    accuracy = (tp + tn) / n if n > 0 else None

    return PolicyMetrics(
        policy_name=policy.name,
        n=n,
        proceed_count=proceed_count,
        stop_count=stop_count,
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        premature_stop_rate=(fn / n) if n > 0 else None,
        unnecessary_continuation_rate=(fp / n) if n > 0 else None,
    )


def run_backtest(
    events: List[TaskEvent],
    policies: Optional[List[Policy]] = None,
) -> BacktestReport:
    """Score each policy in `policies` (default: the five-way comparison
    from `default_baseline_policies()`) against `events`. Returns a report
    whose `render()` honestly says N/A below `_MIN_EVENTS_FOR_METRICS`."""
    policies = policies if policies is not None else default_baseline_policies()

    if len(events) < _MIN_EVENTS_FOR_METRICS:
        return BacktestReport(dataset_size=len(events), policies=[], limitations=_DEFAULT_LIMITATIONS)

    scored = [_score_policy(p, events) for p in policies]
    return BacktestReport(dataset_size=len(events), policies=scored, limitations=_DEFAULT_LIMITATIONS)


def walk_forward_folds(events: List[TaskEvent], n_folds: int = 3) -> List[List[TaskEvent]]:
    """Chronologically partitions `events` (sorted by `timestamp`) into
    `n_folds` contiguous, non-overlapping windows -- a later fold never
    contains an event that precedes an earlier fold's events. This is the
    leakage-prevention primitive section 11 of the project brief asks for;
    see the module docstring for why today's fixed policies don't yet make
    visible use of it."""
    if n_folds < 1:
        raise ValueError(f"n_folds must be >= 1, got {n_folds}")

    ordered = sorted(events, key=lambda e: e.timestamp)
    if not ordered:
        return [[] for _ in range(n_folds)]

    fold_size = max(1, -(-len(ordered) // n_folds))  # ceil division
    folds = [ordered[i : i + fold_size] for i in range(0, len(ordered), fold_size)]
    while len(folds) < n_folds:
        folds.append([])
    return folds[:n_folds]


def run_walk_forward_backtest(
    events: List[TaskEvent],
    policies: Optional[List[Policy]] = None,
    n_folds: int = 3,
) -> Dict[int, BacktestReport]:
    """Runs `run_backtest` independently on each chronological fold from
    `walk_forward_folds`, returning `{fold_index: BacktestReport}`. Each
    fold is evaluated in isolation -- no fold's metrics are computed using
    another fold's events."""
    folds = walk_forward_folds(events, n_folds=n_folds)
    return {i: run_backtest(fold_events, policies=policies) for i, fold_events in enumerate(folds)}

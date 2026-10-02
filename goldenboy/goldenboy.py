"""GoldenBoy: the public composition root.

Every other module added in Stages 1-3 is deliberately a narrow, stateless
building block (`AdaptiveModelRouter.route()`, `PolicyEngine.evaluate()`,
the Stage-3 evaluators, `suggest_escalation()`) with no orchestrator wiring
them together -- see those modules' docstrings and ROADMAP.md's "no giant
orchestration class" non-goal. That non-goal is about auto-wiring inside
*low-level* modules (e.g. `AdaptiveModelRouter` should not call
`PolicyEngine` itself). It is not a prohibition on a top-level, explicit,
caller-visible composition that a human reads top to bottom and can
reason about -- which is exactly what `GoldenBoy.run()` below is: a
`for` loop over a fixed, logged sequence of already-existing steps, each
one a direct call into a Stage 1-3 module, with every step's outcome
written to `AuditStore` as it happens. Nothing here is a hidden pipeline;
a caller who doesn't want this sequencing can keep calling the Stage 1-3
pieces directly instead, same as before.

This mirrors `goldenboy.integration.budget_aware_execution`'s spirit:
compose existing pieces explicitly, log every decision, never silently
retry past what the caller allowed.
"""
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

from goldenboy.adapters.base import GenerationResult, ProviderAdapter
from goldenboy.core.adaptive_router import (
    AdaptiveModelRouter,
    AdaptiveRouterConfig,
    CapabilityRequirements,
    RoutingPlan,
)
from goldenboy.core.audit import AuditEntry, AuditStore, EventType
from goldenboy.core.decision_engine import _complexity_label
from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.escalation import (
    EscalationAction,
    EscalationReason,
    EscalationSuggestion,
    suggest_escalation,
)
from goldenboy.core.estimator import Estimator
from goldenboy.core.governance import ActionRequest, PolicyEngine, PolicyVerdict
from goldenboy.core.model_registry import ModelRegistry, get_default_registry
from goldenboy.core.result_evaluator import (
    EvaluationResult,
    evaluate_json_schema,
    evaluate_required_fields,
    evaluate_truncation,
)
from goldenboy.core.spending import SpendEntry, SpendingStore
from goldenboy.core.task_classifier import TaskClassifier

# Minimum quality floor `GoldenBoy.run()` asks `AdaptiveModelRouter` for on
# the first attempt, when the caller hasn't told us otherwise. "fast" (the
# weakest real quality_class in ModelRegistry's vocabulary) lets the
# router's own strategy (cost_first/quality_first/adaptive) and the
# escalation path (which raises quality on demand) do the actual
# capability-vs-cost trade-off, rather than this facade second-guessing it
# with its own threshold.
_DEFAULT_MIN_QUALITY = "fast"


class GoldenBoyRunError(GoldenBoyError):
    """`GoldenBoy.run()` was called with a request it cannot make sense of
    (e.g. no adapters supplied at all)."""


@dataclass
class AttemptRecord:
    """One real provider call `GoldenBoy.run()` made, plus everything it
    decided about that call. `escalation` is `None` for the attempt that
    either succeeded or was the last one made."""

    plan: RoutingPlan
    generation_result: Optional[GenerationResult]
    evaluation: Optional[EvaluationResult]
    escalation: Optional[EscalationSuggestion] = None


@dataclass
class GoldenBoyRunResult:
    """The outcome of one `GoldenBoy.run()` call."""

    text: str
    sufficient: bool
    final_routing_plan: Optional[RoutingPlan]
    attempts: List[AttemptRecord] = field(default_factory=list)
    total_cost_usd: float = 0.0
    governance_status: str = "allow"  # PolicyVerdict.value: "allow" | "deny" | "require_approval"
    stopped_reason: str = ""


def _estimate_cost_usd(plan: RoutingPlan, result: GenerationResult, registry: ModelRegistry) -> float:
    """Real cost of one actual generation call, from the registry's real
    per-1K pricing and the provider's own reported token counts -- never
    the plan's pre-call *estimate*, which is a different, clearly-named
    number (`RoutingPlan.estimated_cost`)."""
    spec = registry.get(result.provider, result.model)
    if spec is None:
        return 0.0
    return (result.input_tokens / 1000.0) * spec.input_cost_per_1k + (
        result.output_tokens / 1000.0
    ) * spec.output_cost_per_1k


def _escalation_reason_for(evaluation: EvaluationResult, truncation: EvaluationResult) -> EscalationReason:
    """Map a Stage-3 evaluation outcome to the Stage-3 `EscalationReason`
    vocabulary. Truncation is checked first since it's the most specific,
    unambiguous signal (`GenerationResult.truncated`, honestly derived from
    the provider's own stop reason) -- a schema/field failure on top of a
    truncated response is still, first and foremost, a truncation problem."""
    if not truncation.sufficient:
        return EscalationReason.OUTPUT_TRUNCATED
    return EscalationReason.INSUFFICIENT_REASONING


class GoldenBoy:
    """The public facade: classify -> route -> govern -> generate -> record
    spend -> evaluate -> (maybe) escalate and retry, as one explicit,
    audited sequence `GoldenBoy.run()` owns top to bottom.

    Every dependency is caller-supplied or defaulted exactly the way other
    Golden Boy entry points already default them (see `cli.py`): adapters
    are never constructed implicitly from environment variables here --
    that remains the caller's job (see `adapters/base.py`'s docstring).
    """

    def __init__(
        self,
        adapters: Dict[str, ProviderAdapter],
        registry: Optional[ModelRegistry] = None,
        policy_engine: Optional[PolicyEngine] = None,
        spending_store: Optional[SpendingStore] = None,
        router_config: Optional[AdaptiveRouterConfig] = None,
        audit_store: Optional[AuditStore] = None,
        estimator: Optional[Estimator] = None,
        task_classifier: Optional[TaskClassifier] = None,
    ):
        if not adapters:
            raise GoldenBoyRunError(
                "GoldenBoy requires at least one caller-supplied provider adapter "
                "(e.g. {'anthropic': AnthropicAdapter(...)}) -- it does not "
                "construct any adapter itself."
            )
        self.adapters = adapters
        full_registry = registry or get_default_registry()
        # Scope the registry to providers we were actually given an adapter
        # for: routing to a provider with no adapter is always a dead end
        # (step 4 below would just fail with "no adapter supplied"), and
        # scoping it here means the router's own cost/quality comparison --
        # and `suggest_escalation`'s model-escalation search -- never
        # consider a model this GoldenBoy instance has no way to call.
        self.registry = ModelRegistry(
            specs={
                key: spec for key, spec in full_registry.all().items() if spec.provider in adapters
            }
        )
        self.policy_engine = policy_engine or PolicyEngine()
        self.spending_store = spending_store or SpendingStore()
        self.router_config = router_config or AdaptiveRouterConfig.load()
        self.audit_store = audit_store or AuditStore()
        self.estimator = estimator or Estimator()
        self.task_classifier = task_classifier or TaskClassifier()
        self.router = AdaptiveModelRouter(registry=self.registry, config=self.router_config)

    # -- step 1 + step 2 -----------------------------------------------

    def _build_plan(
        self,
        prompt: str,
        task_type: Optional[str],
        capability_requirements: CapabilityRequirements,
        min_quality: str,
        available_budget_usd: float,
    ) -> RoutingPlan:
        estimate = self.estimator.estimate_task(prompt)
        classification = self.task_classifier.classify(prompt)
        effective_task_type = task_type or classification.task_type.value
        complexity_label = _complexity_label(estimate.complexity_score)
        return self.router.route(
            task_type=effective_task_type,
            complexity_label=complexity_label,
            capability_requirements=capability_requirements,
            min_quality=min_quality,
            available_budget_usd=available_budget_usd,
            estimated_input_tokens=estimate.prompt_tokens,
            estimated_output_tokens=estimate.estimated_output_tokens,
        )

    # -- step 3 ----------------------------------------------------------

    def _check_policy(self, plan: RoutingPlan, available_budget_usd: float, task_id: str):
        request = ActionRequest(
            tool=f"generate:{plan.provider}:{plan.model}" if plan.provider else "generate:unrouted",
            task_type=plan.task_type,
            estimated_cost_percentage=0.0,  # this facade governs USD, not the % budget ActionRequest models
        )
        return self.policy_engine.evaluate(request, task_id=task_id)

    def run(
        self,
        prompt: str,
        *,
        task_type: Optional[str] = None,
        capability_requirements: Optional[CapabilityRequirements] = None,
        available_budget_usd: float,
        max_attempts: int = 3,
        required_fields: Optional[List[str]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        min_quality: str = _DEFAULT_MIN_QUALITY,
        task_id: Optional[str] = None,
    ) -> GoldenBoyRunResult:
        """Run `prompt` through the full governed, routed, evaluated,
        escalation-capable pipeline. See module docstring for the step
        sequence; summarized:

            1. classify/estimate (TaskClassifier + Estimator, reused as-is)
            2. build a RoutingPlan (AdaptiveModelRouter)
            3. PolicyEngine.evaluate() -- DENY/REQUIRE_APPROVAL return
               immediately, no provider call
            4. real adapter.generate()
            5. record actual spend (SpendingStore)
            6. evaluate the result (Stage 3 evaluators -- only the ones
               the caller actually asked for, plus truncation always)
            7. if insufficient and attempts remain: suggest_escalation(),
               loop back to step 3 with the new plan; stop on any STOP_*
               action or on max_attempts/budget exhaustion
            8. return GoldenBoyRunResult

        This is the one place in Golden Boy a retry loop is allowed to
        live (see `escalation.py`'s docstring) -- it is a plain, bounded
        `for` loop, never more than `max_attempts` real provider calls.
        """
        if max_attempts < 1:
            raise GoldenBoyRunError(f"max_attempts must be >= 1, got {max_attempts!r}.")

        task_id = task_id or uuid.uuid4().hex
        capability_requirements = capability_requirements or CapabilityRequirements()
        remaining_budget_usd = available_budget_usd
        attempts: List[AttemptRecord] = []
        total_cost_usd = 0.0
        governance_status = "allow"
        stopped_reason = ""

        self.audit_store.record(
            AuditEntry.create(action=EventType.TASK_STARTED, result="success", task_id=task_id)
        )

        # Steps 1 + 2: classify/estimate, build the first RoutingPlan.
        plan = self._build_plan(
            prompt, task_type, capability_requirements, min_quality, remaining_budget_usd
        )
        self.audit_store.record(
            AuditEntry.create(
                action=EventType.ESTIMATE_CREATED,
                result="success",
                task_id=task_id,
                extra={
                    "task_type": plan.task_type,
                    "complexity_label": plan.complexity,
                    "provider": plan.provider,
                    "model": plan.model,
                },
            )
        )

        final_plan: Optional[RoutingPlan] = plan
        last_text = ""

        for attempt_index in range(1, max_attempts + 1):
            final_plan = plan

            # Step 3: governance, every attempt (a new/escalated plan is a
            # new decision, not a rubber stamp of the first one).
            policy_result = self._check_policy(plan, remaining_budget_usd, task_id)
            governance_status = policy_result.verdict.value

            if policy_result.verdict is PolicyVerdict.DENY:
                stopped_reason = f"DENY: {policy_result.reason}"
                return GoldenBoyRunResult(
                    text="", sufficient=False, final_routing_plan=plan, attempts=attempts,
                    total_cost_usd=total_cost_usd, governance_status=governance_status,
                    stopped_reason=stopped_reason,
                )
            if policy_result.verdict is PolicyVerdict.REQUIRE_APPROVAL:
                stopped_reason = f"REQUIRE_APPROVAL: {policy_result.reason}"
                return GoldenBoyRunResult(
                    text="", sufficient=False, final_routing_plan=plan, attempts=attempts,
                    total_cost_usd=total_cost_usd, governance_status=governance_status,
                    stopped_reason=stopped_reason,
                )

            if plan.provider is None or plan.model is None:
                stopped_reason = (
                    "No registered model satisfies the requested capabilities/quality under "
                    "the available budget -- see RoutingPlan.reasoning."
                )
                break

            adapter = self.adapters.get(plan.provider)
            if adapter is None:
                stopped_reason = (
                    f"No adapter supplied for provider '{plan.provider}' "
                    f"(routed model: {plan.provider}:{plan.model})."
                )
                self.audit_store.record(
                    AuditEntry.create(
                        action=EventType.ACTION_EXECUTED, result="failure", task_id=task_id,
                        error=stopped_reason,
                    )
                )
                break

            # Step 4: the real generation call.
            self.audit_store.record(
                AuditEntry.create(
                    action=EventType.ACTION_ALLOWED, result="success", task_id=task_id,
                    tool=f"{plan.provider}:{plan.model}", decision=policy_result.verdict.value,
                    policy_result=policy_result.reason_code,
                )
            )
            start = time.monotonic()
            try:
                generation_result = adapter.generate(
                    prompt, max_output_tokens=plan.output_budget_tokens
                )
            except Exception as e:  # noqa: BLE001 - a provider failure is a real, expected outcome here
                duration = time.monotonic() - start
                self.audit_store.record(
                    AuditEntry.create(
                        action=EventType.ACTION_EXECUTED, result="failure", task_id=task_id,
                        tool=f"{plan.provider}:{plan.model}", error=str(e),
                        duration_seconds=duration,
                    )
                )
                attempts.append(
                    AttemptRecord(plan=plan, generation_result=None, evaluation=None)
                )
                if attempt_index >= max_attempts:
                    stopped_reason = "STOP_MAX_ATTEMPTS"
                    break
                suggestion = suggest_escalation(
                    EscalationReason.PROVIDER_FAILURE, plan, self.registry,
                    attempt_index, max_attempts,
                )
                attempts[-1].escalation = suggestion
                self.audit_store.record(
                    AuditEntry.create(
                        action=EventType.RETRY_STARTED, result="success", task_id=task_id,
                        extra={"escalation_action": suggestion.action.value},
                    )
                )
                if suggestion.action in (
                    EscalationAction.STOP_BUDGET_EXHAUSTED,
                    EscalationAction.STOP_MAX_ATTEMPTS,
                ):
                    stopped_reason = suggestion.action.value
                    break
                plan = self._apply_suggestion(plan, suggestion)
                continue

            duration = time.monotonic() - start

            # Step 5: record actual spend (real tokens, real registry pricing).
            actual_cost_usd = _estimate_cost_usd(plan, generation_result, self.registry)
            total_cost_usd += actual_cost_usd
            remaining_budget_usd -= actual_cost_usd
            self.spending_store.append(
                SpendEntry.create(
                    label=task_id,
                    estimated_tokens=plan.input_budget_tokens + plan.output_budget_tokens,
                    actual_tokens=generation_result.input_tokens + generation_result.output_tokens,
                    task_type=plan.task_type,
                    extra={"provider": plan.provider, "model": plan.model},
                )
            )
            self.audit_store.record(
                AuditEntry.create(
                    action=EventType.ACTION_EXECUTED, result="success", task_id=task_id,
                    tool=f"{plan.provider}:{plan.model}", actual_cost=actual_cost_usd,
                    duration_seconds=duration,
                )
            )

            # Step 6: evaluate -- only the checks the caller actually asked for.
            evaluation = self._evaluate(generation_result, required_fields, json_schema)
            attempts.append(
                AttemptRecord(plan=plan, generation_result=generation_result, evaluation=evaluation)
            )
            last_text = generation_result.text
            final_plan = plan

            if evaluation.sufficient:
                self.audit_store.record(
                    AuditEntry.create(action=EventType.TASK_COMPLETED, result="success", task_id=task_id)
                )
                return GoldenBoyRunResult(
                    text=generation_result.text, sufficient=True, final_routing_plan=plan,
                    attempts=attempts, total_cost_usd=total_cost_usd,
                    governance_status=governance_status, stopped_reason="sufficient",
                )

            self.audit_store.record(
                AuditEntry.create(
                    action=EventType.VERIFICATION_FAILED, result="failure", task_id=task_id,
                    error=evaluation.reason,
                )
            )

            # Step 7: bounded escalation.
            if attempt_index >= max_attempts:
                stopped_reason = "STOP_MAX_ATTEMPTS"
                break
            if remaining_budget_usd <= 0:
                stopped_reason = "STOP_BUDGET_EXHAUSTED"
                break

            truncation = evaluate_truncation(generation_result)
            reason = _escalation_reason_for(evaluation, truncation)
            suggestion = suggest_escalation(
                reason, plan, self.registry, attempt_index, max_attempts
            )
            attempts[-1].escalation = suggestion
            self.audit_store.record(
                AuditEntry.create(
                    action=EventType.RETRY_STARTED, result="success", task_id=task_id,
                    extra={"escalation_action": suggestion.action.value},
                )
            )

            if suggestion.action in (
                EscalationAction.STOP_BUDGET_EXHAUSTED,
                EscalationAction.STOP_MAX_ATTEMPTS,
            ):
                stopped_reason = suggestion.action.value
                break

            plan = self._apply_suggestion(plan, suggestion)

        self.audit_store.record(
            AuditEntry.create(
                action=EventType.TASK_COMPLETED, result="failure", task_id=task_id,
                error=stopped_reason or "STOP_MAX_ATTEMPTS",
            )
        )
        return GoldenBoyRunResult(
            text=last_text, sufficient=False, final_routing_plan=final_plan, attempts=attempts,
            total_cost_usd=total_cost_usd, governance_status=governance_status,
            stopped_reason=stopped_reason or "STOP_MAX_ATTEMPTS",
        )

    @staticmethod
    def _apply_suggestion(plan: RoutingPlan, suggestion: EscalationSuggestion) -> RoutingPlan:
        if suggestion.new_routing_plan is not None:
            return suggestion.new_routing_plan
        if suggestion.new_output_budget_tokens is not None:
            return replace(plan, output_budget_tokens=suggestion.new_output_budget_tokens)
        # ESCALATE_MODEL/FALLBACK_PROVIDER always set new_routing_plan, and
        # INCREASE_OUTPUT_BUDGET always sets new_output_budget_tokens (see
        # escalation.py) -- this branch is only reachable if a future
        # EscalationAction is added without updating this facade, so fail
        # loudly rather than silently retrying the identical plan forever.
        raise GoldenBoyRunError(
            f"EscalationSuggestion(action={suggestion.action!r}) carries neither a new "
            "routing plan nor a new output budget -- GoldenBoy.run() doesn't know how to "
            "apply it."
        )

    @staticmethod
    def _evaluate(
        result: GenerationResult,
        required_fields: Optional[List[str]],
        json_schema: Optional[Dict[str, Any]],
    ) -> EvaluationResult:
        """Truncation is always checked (a truncated result is never
        sufficient regardless of anything else); schema/field checks only
        run when the caller actually supplied them -- forcing schema
        validation with no schema would be inventing a requirement the
        caller never asked for."""
        truncation = evaluate_truncation(result)
        if not truncation.sufficient:
            return truncation

        if json_schema is not None:
            schema_result = evaluate_json_schema(result.text, json_schema)
            if not schema_result.sufficient:
                return schema_result

        if required_fields:
            fields_result = evaluate_required_fields(result.text, required_fields)
            if not fields_result.sufficient:
                return fields_result

        return EvaluationResult(
            sufficient=True,
            reason="Not truncated and all caller-requested checks passed.",
            evidence={"truncation_condition": truncation.evidence.get("truncation_condition")},
        )

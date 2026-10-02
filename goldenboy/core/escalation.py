"""Escalation building blocks: pure functions that suggest ONE next step
after an attempt was judged insufficient (see `result_evaluator.py`).

This is deliberately NOT an orchestrator. There is no class here that
calls `generate()` in a loop, retries anything, or owns a PLAN->EXECUTE->
TEST->DIAGNOSE->RETRY cycle -- ROADMAP.md names exactly that shape as a
non-goal ("exactly the one giant orchestration class the brief warns
against"). `suggest_escalation` takes a snapshot of the current situation
and returns a suggestion; it does not execute it, does not loop, and does
not call any provider. Composing these suggestions into an actual retry
loop is left to the caller (or a future Stage-4 public API) -- adding a
"convenience" while-loop class here was considered and deliberately not
done.

The one non-negotiable safety invariant -- no infinite retry -- is
enforced as a pure check inside this pure function: `suggest_escalation`
itself refuses (returns `STOP_MAX_ATTEMPTS`) once
`attempt_count >= max_attempts`, regardless of `reason`. A caller that
ignores the suggestion and calls generate() again anyway is not something
this module can prevent -- that enforcement point is a stateful loop the
caller owns, which this module is not.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from goldenboy.core.adaptive_router import (
    _QUALITY_RANK,
    AdaptiveModelRouter,
    RoutingPlan,
)
from goldenboy.core.model_registry import ModelRegistry
from goldenboy.core.token_optimizer import compute_output_budget_tokens

# Models at/above this fraction of their max_output_tokens are treated as
# "already maxed out" -- increasing the output budget further wouldn't
# meaningfully help, so escalate the model instead. A fixed, documented
# threshold, not a tuned figure.
_OUTPUT_BUDGET_NEAR_MAX_FRACTION = 0.95

# Escalate-model suggestions use a very large budget sentinel because this
# function only *suggests* a next step -- it does not enforce a real-money
# budget (that's the caller's own governance/spending layer, per this
# codebase's "no auto-wiring" convention: see adaptive_router.py and
# governance.py). Using `float("inf")` here means the suggestion is driven
# purely by capability/quality fit, exactly like `quality_first` routing;
# the caller is still responsible for checking the suggested plan's
# `estimated_cost`/`fits_budget` against its own real budget before acting
# on it.
_UNBOUNDED_BUDGET_USD = float("inf")

_RANK_TO_QUALITY = {rank: name for name, rank in _QUALITY_RANK.items()}


class EscalationReason(Enum):
    """Why the last attempt was judged insufficient. `INSUFFICIENT_REASONING`
    and `MISSING_CONTEXT` are caller-asserted -- this module does not add
    any new ML/heuristic signal to auto-detect them; the caller decides,
    e.g. from its own evaluation of the result."""

    OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
    INSUFFICIENT_REASONING = "INSUFFICIENT_REASONING"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class EscalationAction(Enum):
    INCREASE_OUTPUT_BUDGET = "INCREASE_OUTPUT_BUDGET"
    ESCALATE_MODEL = "ESCALATE_MODEL"
    FALLBACK_PROVIDER = "FALLBACK_PROVIDER"
    STOP_BUDGET_EXHAUSTED = "STOP_BUDGET_EXHAUSTED"
    STOP_MAX_ATTEMPTS = "STOP_MAX_ATTEMPTS"


@dataclass(frozen=True)
class EscalationSuggestion:
    """ONE suggested next step. Never executed by this module -- the
    caller decides whether and how to act on it."""

    action: EscalationAction
    reason: str
    new_output_budget_tokens: Optional[int] = None
    new_routing_plan: Optional[RoutingPlan] = None


def _escalate_model_plan(
    current_plan: RoutingPlan, registry: ModelRegistry
) -> Optional[RoutingPlan]:
    """Ask `AdaptiveModelRouter` (never duplicating its filtering logic)
    for the highest-quality qualifying model, one quality rank above the
    current plan's model where possible. Returns None if nothing in the
    registry qualifies (router already handles that honestly via
    `fits_budget=False` / `provider is None`)."""
    current_spec = (
        registry.get(current_plan.provider, current_plan.model)
        if current_plan.provider and current_plan.model
        else None
    )
    current_rank = _QUALITY_RANK[current_spec.quality_class] if current_spec else 0
    target_rank = min(current_rank + 1, max(_QUALITY_RANK.values()))
    target_quality = _RANK_TO_QUALITY[target_rank]

    router = AdaptiveModelRouter(registry=registry)
    router.config.strategy = "quality_first"

    new_plan = router.route(
        task_type=current_plan.task_type,
        complexity_label=current_plan.complexity,
        capability_requirements=current_plan.capability_requirements_used,
        min_quality=target_quality,
        available_budget_usd=_UNBOUNDED_BUDGET_USD,
        estimated_input_tokens=current_plan.input_budget_tokens,
        estimated_output_tokens=current_plan.output_budget_tokens,
    )
    if new_plan.provider is None:
        return None
    if (new_plan.provider, new_plan.model) == (current_plan.provider, current_plan.model):
        return None
    return new_plan


def suggest_escalation(
    reason: EscalationReason,
    current_plan: RoutingPlan,
    registry: ModelRegistry,
    attempt_count: int,
    max_attempts: int,
) -> EscalationSuggestion:
    """Pure function: given why the last attempt failed and the current
    routing plan, suggest ONE next step. Never executes anything, never
    loops, never calls a provider.

    Hard cap (non-negotiable): once `attempt_count >= max_attempts`, this
    always returns `STOP_MAX_ATTEMPTS`, regardless of `reason` -- checked
    first, before any reason-specific logic."""
    if attempt_count >= max_attempts:
        return EscalationSuggestion(
            action=EscalationAction.STOP_MAX_ATTEMPTS,
            reason=(
                f"attempt_count ({attempt_count}) >= max_attempts ({max_attempts}): "
                "refusing to suggest another escalation."
            ),
        )

    if reason is EscalationReason.BUDGET_EXHAUSTED:
        return EscalationSuggestion(
            action=EscalationAction.STOP_BUDGET_EXHAUSTED,
            reason="Caller reported budget exhausted; no escalation can fix that -- stop.",
        )

    if reason is EscalationReason.PROVIDER_FAILURE:
        if current_plan.fallback_chain:
            fallback_provider, fallback_model = current_plan.fallback_chain[0]
            fallback_spec = registry.get(fallback_provider, fallback_model)
            new_plan = RoutingPlan(
                task_type=current_plan.task_type,
                complexity=current_plan.complexity,
                provider=fallback_provider,
                model=fallback_model,
                reasoning=(
                    f"FALLBACK_PROVIDER: current plan's provider failed; falling back to "
                    f"the next real qualifying model in its own fallback_chain "
                    f"({fallback_provider}:{fallback_model})."
                ),
                input_budget_tokens=current_plan.input_budget_tokens,
                output_budget_tokens=current_plan.output_budget_tokens,
                estimated_cost=None,
                fallback_chain=current_plan.fallback_chain[1:],
                capability_requirements_used=current_plan.capability_requirements_used,
                fits_budget=fallback_spec is not None,
            )
            return EscalationSuggestion(
                action=EscalationAction.FALLBACK_PROVIDER,
                reason=(
                    f"Provider failure on {current_plan.provider}:{current_plan.model}; "
                    f"falling back to {fallback_provider}:{fallback_model} from the "
                    f"current plan's own fallback_chain."
                ),
                new_routing_plan=new_plan,
            )
        # No fallback available -- escalate model instead, same as the
        # reasoning/context-insufficiency path below.
        escalated = _escalate_model_plan(current_plan, registry)
        if escalated is not None:
            return EscalationSuggestion(
                action=EscalationAction.ESCALATE_MODEL,
                reason=(
                    "Provider failure and no fallback_chain entry available; "
                    "escalating to a different, higher-quality registered model instead."
                ),
                new_routing_plan=escalated,
            )
        return EscalationSuggestion(
            action=EscalationAction.STOP_MAX_ATTEMPTS,
            reason=(
                "Provider failure, no fallback_chain entry, and no stronger registered "
                "model qualifies -- nothing left to suggest."
            ),
        )

    if reason is EscalationReason.OUTPUT_TRUNCATED:
        current_spec = (
            registry.get(current_plan.provider, current_plan.model)
            if current_plan.provider and current_plan.model
            else None
        )
        if current_spec is not None:
            near_max = current_plan.output_budget_tokens >= (
                current_spec.max_output_tokens * _OUTPUT_BUDGET_NEAR_MAX_FRACTION
            )
            if not near_max:
                new_budget = compute_output_budget_tokens(1.0, current_spec)
                if new_budget > current_plan.output_budget_tokens:
                    return EscalationSuggestion(
                        action=EscalationAction.INCREASE_OUTPUT_BUDGET,
                        reason=(
                            f"Output was truncated at {current_plan.output_budget_tokens} tokens; "
                            f"{current_spec.provider}:{current_spec.model} supports up to "
                            f"{current_spec.max_output_tokens}, so raising the output budget to "
                            f"{new_budget}."
                        ),
                        new_output_budget_tokens=new_budget,
                    )
        # Already near/at the model's own max output -- a bigger budget on
        # the *same* model won't help; escalate to a different model.
        escalated = _escalate_model_plan(current_plan, registry)
        if escalated is not None:
            return EscalationSuggestion(
                action=EscalationAction.ESCALATE_MODEL,
                reason=(
                    "Output was truncated and the current model is already at/near its own "
                    "max_output_tokens; escalating to a different, higher-quality registered "
                    "model instead of raising the budget further."
                ),
                new_routing_plan=escalated,
            )
        return EscalationSuggestion(
            action=EscalationAction.STOP_MAX_ATTEMPTS,
            reason=(
                "Output was truncated, the current model is at its max output budget, and no "
                "stronger registered model qualifies -- nothing left to suggest."
            ),
        )

    # INSUFFICIENT_REASONING / MISSING_CONTEXT: caller asserts the model
    # itself wasn't capable/informed enough -- escalate to a stronger model.
    escalated = _escalate_model_plan(current_plan, registry)
    if escalated is not None:
        return EscalationSuggestion(
            action=EscalationAction.ESCALATE_MODEL,
            reason=(
                f"Caller reported {reason.value}; escalating to a different, higher-quality "
                "registered model."
            ),
            new_routing_plan=escalated,
        )
    return EscalationSuggestion(
        action=EscalationAction.STOP_MAX_ATTEMPTS,
        reason=(
            f"Caller reported {reason.value}, but no stronger registered model qualifies -- "
            "nothing left to suggest."
        ),
    )

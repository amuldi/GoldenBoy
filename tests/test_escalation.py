from goldenboy.core.adaptive_router import CapabilityRequirements, RoutingPlan
from goldenboy.core.escalation import (
    EscalationAction,
    EscalationReason,
    EscalationSuggestion,
    suggest_escalation,
)
from goldenboy.core.model_registry import get_default_registry


def _plan(
    provider="anthropic",
    model="claude-haiku-4-5",
    output_budget_tokens=1000,
    fallback_chain=None,
) -> RoutingPlan:
    return RoutingPlan(
        task_type="generic",
        complexity="MEDIUM",
        provider=provider,
        model=model,
        reasoning="test plan",
        input_budget_tokens=500,
        output_budget_tokens=output_budget_tokens,
        estimated_cost=0.01,
        fallback_chain=fallback_chain or [],
        capability_requirements_used=CapabilityRequirements(),
        fits_budget=True,
    )


REGISTRY = get_default_registry()


class TestMaxAttemptsHardStop:
    def test_stops_when_attempt_count_at_max(self):
        suggestion = suggest_escalation(
            EscalationReason.OUTPUT_TRUNCATED, _plan(), REGISTRY, attempt_count=3, max_attempts=3
        )
        assert suggestion.action is EscalationAction.STOP_MAX_ATTEMPTS

    def test_stops_when_attempt_count_exceeds_max(self):
        suggestion = suggest_escalation(
            EscalationReason.INSUFFICIENT_REASONING, _plan(), REGISTRY, attempt_count=5, max_attempts=3
        )
        assert suggestion.action is EscalationAction.STOP_MAX_ATTEMPTS

    def test_enforced_even_if_caller_keeps_calling(self):
        # Caller ignores the first stop and calls again -- function must
        # refuse again, not escalate just because it's being asked harder.
        for attempt in range(3, 10):
            suggestion = suggest_escalation(
                EscalationReason.PROVIDER_FAILURE, _plan(), REGISTRY, attempt_count=attempt, max_attempts=3
            )
            assert suggestion.action is EscalationAction.STOP_MAX_ATTEMPTS

    def test_allowed_below_max_attempts(self):
        suggestion = suggest_escalation(
            EscalationReason.OUTPUT_TRUNCATED, _plan(), REGISTRY, attempt_count=1, max_attempts=3
        )
        assert suggestion.action is not EscalationAction.STOP_MAX_ATTEMPTS


class TestBudgetExhausted:
    def test_returns_stop_budget_exhausted(self):
        suggestion = suggest_escalation(
            EscalationReason.BUDGET_EXHAUSTED, _plan(), REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.STOP_BUDGET_EXHAUSTED
        assert suggestion.new_routing_plan is None
        assert suggestion.new_output_budget_tokens is None

    def test_budget_exhausted_wins_even_with_attempts_left(self):
        suggestion = suggest_escalation(
            EscalationReason.BUDGET_EXHAUSTED, _plan(), REGISTRY, attempt_count=0, max_attempts=100
        )
        assert suggestion.action is EscalationAction.STOP_BUDGET_EXHAUSTED


class TestOutputTruncated:
    def test_increases_output_budget_when_room_remains(self):
        plan = _plan(model="claude-haiku-4-5", output_budget_tokens=1000)
        suggestion = suggest_escalation(
            EscalationReason.OUTPUT_TRUNCATED, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.INCREASE_OUTPUT_BUDGET
        assert suggestion.new_output_budget_tokens is not None
        assert suggestion.new_output_budget_tokens > plan.output_budget_tokens

    def test_escalates_model_when_already_near_max_output(self):
        spec = REGISTRY.get("anthropic", "claude-haiku-4-5")
        plan = _plan(model="claude-haiku-4-5", output_budget_tokens=spec.max_output_tokens)
        suggestion = suggest_escalation(
            EscalationReason.OUTPUT_TRUNCATED, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.ESCALATE_MODEL
        assert suggestion.new_routing_plan is not None
        assert (suggestion.new_routing_plan.provider, suggestion.new_routing_plan.model) != (
            plan.provider,
            plan.model,
        )


class TestInsufficientReasoningAndMissingContext:
    def test_insufficient_reasoning_escalates_model(self):
        plan = _plan(model="claude-haiku-4-5")
        suggestion = suggest_escalation(
            EscalationReason.INSUFFICIENT_REASONING, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.ESCALATE_MODEL
        new_plan = suggestion.new_routing_plan
        assert new_plan is not None
        # Must be a real, different model actually present in the registry.
        assert REGISTRY.get(new_plan.provider, new_plan.model) is not None
        assert (new_plan.provider, new_plan.model) != (plan.provider, plan.model)

    def test_missing_context_escalates_model(self):
        plan = _plan(model="claude-haiku-4-5")
        suggestion = suggest_escalation(
            EscalationReason.MISSING_CONTEXT, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.ESCALATE_MODEL
        assert suggestion.new_routing_plan is not None

    def test_already_at_frontier_quality_has_nothing_stronger(self):
        # claude-opus-4-1 is already "frontier" -- the highest quality rank
        # in the registry, so there is nothing stronger to escalate to.
        plan = _plan(model="claude-opus-4-1")
        suggestion = suggest_escalation(
            EscalationReason.INSUFFICIENT_REASONING, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.STOP_MAX_ATTEMPTS
        assert suggestion.new_routing_plan is None


class TestProviderFailure:
    def test_uses_fallback_chain_when_present(self):
        plan = _plan(
            model="claude-haiku-4-5",
            fallback_chain=[("openai", "gpt-4o-mini"), ("anthropic", "claude-sonnet-4-5")],
        )
        suggestion = suggest_escalation(
            EscalationReason.PROVIDER_FAILURE, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.FALLBACK_PROVIDER
        assert suggestion.new_routing_plan.provider == "openai"
        assert suggestion.new_routing_plan.model == "gpt-4o-mini"
        assert REGISTRY.get("openai", "gpt-4o-mini") is not None

    def test_escalates_model_when_no_fallback_chain(self):
        plan = _plan(model="claude-haiku-4-5", fallback_chain=[])
        suggestion = suggest_escalation(
            EscalationReason.PROVIDER_FAILURE, plan, REGISTRY, attempt_count=0, max_attempts=3
        )
        assert suggestion.action is EscalationAction.ESCALATE_MODEL
        assert suggestion.new_routing_plan is not None


def test_suggestion_is_frozen_dataclass_instance():
    suggestion = suggest_escalation(
        EscalationReason.BUDGET_EXHAUSTED, _plan(), REGISTRY, attempt_count=0, max_attempts=3
    )
    assert isinstance(suggestion, EscalationSuggestion)
    assert isinstance(suggestion.reason, str) and suggestion.reason

"""Tests for the `GoldenBoy` public API facade (`goldenboy/goldenboy.py`).

Uses `MockProvider` (deterministic, no network) as the adapter under test,
plus a small `FakeTruncatingAdapter` for tests that need precise control
over truncation/cost across successive attempts -- `MockProvider`'s
truncation is derived from word count vs. `max_output_tokens`, which is
hard to pin down exactly once `AdaptiveModelRouter`'s own output-budget
formula is in the loop.
"""
from typing import Optional

import pytest

from goldenboy.adapters.base import GenerationResult, ProviderAdapter
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.audit import AuditStore
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.governance import PolicyConfig, PolicyEngine
from goldenboy.core.spending import SpendingStore
from goldenboy.goldenboy import GoldenBoy, GoldenBoyRunError


class FakeTruncatingAdapter(ProviderAdapter):
    """A test-only adapter whose `generate()` behavior is scripted call by
    call, so escalation/budget/attempt-count tests don't depend on
    `AdaptiveModelRouter`'s real output-budget formula lining up with
    `MockProvider`'s word-count truncation rule."""

    provider_name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5", scripted_results=None):
        self.model = model
        self._scripted = list(scripted_results or [])
        self.call_count = 0

    def get_available_budget(self) -> Budget:
        return Budget(remaining_percentage=100.0, source="fake", confidence=UsageConfidence.EXACT)

    def generate(self, prompt: str, *, max_output_tokens: int, reasoning_effort: Optional[str] = None):
        result = self._scripted[min(self.call_count, len(self._scripted) - 1)]
        self.call_count += 1
        return result


def _truncated_result(output_tokens: int = 50) -> GenerationResult:
    return GenerationResult(
        text="truncated...",
        input_tokens=10,
        output_tokens=output_tokens,
        stop_reason="max_tokens",
        truncated=True,
        latency_ms=1.0,
        model="claude-haiku-4-5",
        provider="anthropic",
    )


def _ok_result(text: str = "done, LOGINBUG fixed") -> GenerationResult:
    return GenerationResult(
        text=text,
        input_tokens=10,
        output_tokens=20,
        stop_reason="end_turn",
        truncated=False,
        latency_ms=1.0,
        model="claude-haiku-4-5",
        provider="anthropic",
    )


def _mock_adapters():
    anthropic = MockProvider(model="claude-haiku-4-5")
    anthropic.provider_name = "anthropic"
    openai = MockProvider(model="gpt-4o-mini")
    openai.provider_name = "openai"
    return {"anthropic": anthropic, "openai": openai}


@pytest.fixture
def audit_store(tmp_path):
    return AuditStore(history_dir=str(tmp_path / ".goldenboy"))


@pytest.fixture
def spending_store(tmp_path):
    return SpendingStore(history_dir=str(tmp_path / ".goldenboy"))


# --- construction -------------------------------------------------------

def test_requires_at_least_one_adapter(audit_store, spending_store):
    with pytest.raises(GoldenBoyRunError):
        GoldenBoy(adapters={}, audit_store=audit_store, spending_store=spending_store)


# --- DENY path -----------------------------------------------------------

def test_deny_path_returns_immediately_no_generate_call(audit_store, spending_store):
    adapters = _mock_adapters()
    # Discover the routed tool deterministically, then deny exactly that.
    from goldenboy.core.adaptive_router import CapabilityRequirements
    probe = GoldenBoy(adapters=adapters, audit_store=audit_store, spending_store=spending_store)
    plan = probe._build_plan("fix a bug", None, CapabilityRequirements(), "fast", 10.0)
    tool_name = f"generate:{plan.provider}:{plan.model}"

    policy = PolicyEngine(config=PolicyConfig(denied_tools=[tool_name]))
    gb = GoldenBoy(
        adapters=adapters, policy_engine=policy, audit_store=audit_store, spending_store=spending_store,
    )

    calls = []
    for adapter in adapters.values():
        original = adapter.generate
        def wrapped(*a, _orig=original, **kw):
            calls.append(1)
            return _orig(*a, **kw)
        adapter.generate = wrapped

    result = gb.run("fix a bug", available_budget_usd=10.0, max_attempts=3)

    assert result.sufficient is False
    assert result.governance_status == "deny"
    assert result.stopped_reason.startswith("DENY:")
    assert result.attempts == []
    assert calls == []


# --- REQUIRE_APPROVAL path -------------------------------------------------

def test_require_approval_path_returns_immediately_no_generate_call(audit_store, spending_store):
    adapters = _mock_adapters()
    probe = GoldenBoy(adapters=adapters, audit_store=audit_store, spending_store=spending_store)
    from goldenboy.core.adaptive_router import CapabilityRequirements
    plan = probe._build_plan("fix a bug", None, CapabilityRequirements(), "fast", 10.0)
    tool_name = f"generate:{plan.provider}:{plan.model}"

    policy = PolicyEngine(config=PolicyConfig(approval_required_tools=[tool_name]))
    gb = GoldenBoy(
        adapters=adapters, policy_engine=policy, audit_store=audit_store, spending_store=spending_store,
    )

    calls = []
    for adapter in adapters.values():
        original = adapter.generate
        def wrapped(*a, _orig=original, **kw):
            calls.append(1)
            return _orig(*a, **kw)
        adapter.generate = wrapped

    result = gb.run("fix a bug", available_budget_usd=10.0, max_attempts=3)

    assert result.sufficient is False
    assert result.governance_status == "require_approval"
    assert result.stopped_reason.startswith("REQUIRE_APPROVAL:")
    assert result.attempts == []
    assert calls == []


# --- ALLOW, sufficient first attempt ---------------------------------------

def test_allow_sufficient_first_attempt_one_attempt_recorded(audit_store, spending_store):
    adapters = _mock_adapters()
    gb = GoldenBoy(adapters=adapters, audit_store=audit_store, spending_store=spending_store)

    result = gb.run("fix a bug in the login flow", available_budget_usd=10.0, max_attempts=3)

    assert result.sufficient is True
    assert result.governance_status == "allow"
    assert result.stopped_reason == "sufficient"
    assert len(result.attempts) == 1
    assert result.attempts[0].generation_result is not None
    assert result.text == result.attempts[0].generation_result.text
    assert result.total_cost_usd >= 0.0
    assert result.final_routing_plan is not None


# --- ALLOW, insufficient first attempt escalating to a second that succeeds --

def test_insufficient_first_attempt_escalates_and_succeeds(audit_store, spending_store):
    adapter = FakeTruncatingAdapter(
        scripted_results=[_truncated_result(output_tokens=50), _ok_result()]
    )
    gb = GoldenBoy(adapters={"anthropic": adapter}, audit_store=audit_store, spending_store=spending_store)

    result = gb.run(
        "fix the LOGINBUG in the login flow", available_budget_usd=10.0, max_attempts=3,
        required_fields=["LOGINBUG"],
    )

    assert result.sufficient is True
    assert len(result.attempts) == 2
    assert result.attempts[0].evaluation.sufficient is False
    assert result.attempts[0].escalation is not None
    assert result.attempts[1].evaluation.sufficient is True
    assert adapter.call_count == 2
    expected_cost = sum(
        (a.generation_result.input_tokens / 1000.0) * 0.001
        + (a.generation_result.output_tokens / 1000.0) * 0.005
        for a in result.attempts
    )
    assert result.total_cost_usd == pytest.approx(expected_cost)


# --- max_attempts exhausted --------------------------------------------------

def test_max_attempts_exhausted_stops_at_exactly_max_attempts(audit_store, spending_store):
    adapter = FakeTruncatingAdapter(
        scripted_results=[_truncated_result(output_tokens=50)] * 5
    )
    gb = GoldenBoy(adapters={"anthropic": adapter}, audit_store=audit_store, spending_store=spending_store)

    result = gb.run(
        "fix the LOGINBUG", available_budget_usd=1000.0, max_attempts=2, required_fields=["NEVER_PRESENT"],
    )

    assert result.sufficient is False
    assert result.stopped_reason == "STOP_MAX_ATTEMPTS"
    assert adapter.call_count == 2
    assert len(result.attempts) == 2


# --- budget exhausted mid-escalation ----------------------------------------

def test_budget_exhausted_mid_escalation_stops_cleanly(audit_store, spending_store):
    # A huge truncated output drives real cost (registry-priced) well past
    # a small available budget, so the facade must stop before a second call.
    adapter = FakeTruncatingAdapter(
        scripted_results=[_truncated_result(output_tokens=500_000)] * 3
    )
    gb = GoldenBoy(adapters={"anthropic": adapter}, audit_store=audit_store, spending_store=spending_store)

    result = gb.run("fix the LOGINBUG", available_budget_usd=1.0, max_attempts=5)

    assert result.sufficient is False
    assert result.stopped_reason == "STOP_BUDGET_EXHAUSTED"
    assert adapter.call_count == 1
    assert len(result.attempts) == 1


# --- audit log side effects --------------------------------------------------

def test_audit_store_receives_entries_for_each_step(audit_store, spending_store):
    adapters = _mock_adapters()
    gb = GoldenBoy(adapters=adapters, audit_store=audit_store, spending_store=spending_store)

    result = gb.run("fix a bug in the login flow", available_budget_usd=10.0, max_attempts=3)
    assert result.sufficient is True

    events = audit_store.load_events().events
    actions = [e.action for e in events]
    assert "task_started" in actions
    assert "estimate_created" in actions
    assert "action_allowed" in actions
    assert "action_executed" in actions
    assert "task_completed" in actions
    # Every entry carries the same task_id this run used.
    task_ids = {e.task_id for e in events}
    assert len(task_ids) == 1
    assert None not in task_ids

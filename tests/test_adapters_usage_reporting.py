"""Verifies the Anthropic/OpenAI adapters report usage honestly:
- before any refresh, confidence is UNKNOWN (not a fabricated 100%-as-fact)
- execute_unit is no longer implemented (no more faking task execution)
- after a refresh, confidence is ESTIMATED and source is labeled, never EXACT
- confidence ages from ESTIMATED to STALE once stale_after_seconds passes,
  using an injected fake clock -- no real sleeping in these tests

Requires the `anthropic`/`openai` optional extras; skips cleanly if absent.
"""
import pytest

from goldenboy.core.budget import UsageConfidence
from goldenboy.core.config import GoldenBoyConfig

anthropic = pytest.importorskip("anthropic")
openai = pytest.importorskip("openai")


class _FakeClock:
    """A settable clock for deterministic staleness tests -- advances only
    when told to, never by real elapsed wall-clock time."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _fake_anthropic_response(remaining="40000", total="100000"):
    class _FakeResponse:
        headers = {
            "anthropic-ratelimit-tokens-remaining": remaining,
            "anthropic-ratelimit-tokens-limit": total,
        }

    return _FakeResponse()


def _fake_openai_response(remaining="25000", total="100000"):
    class _FakeResponse:
        headers = {
            "x-ratelimit-remaining-tokens": remaining,
            "x-ratelimit-limit-tokens": total,
        }

    return _FakeResponse()


def test_anthropic_adapter_reports_unknown_before_refresh(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter()
    budget = adapter.get_available_budget()

    assert budget.confidence == UsageConfidence.UNKNOWN
    assert budget.source == "anthropic_rate_limit_headers"


def test_anthropic_adapter_execute_unit_is_not_implemented(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter
    from goldenboy.core.priorities import ExecutionUnit, Priority

    adapter = AnthropicAdapter()
    unit = ExecutionUnit("1", "Do the actual coding task", Priority.P0)

    with pytest.raises(NotImplementedError):
        adapter.execute_unit(unit)


def test_anthropic_adapter_refresh_updates_confidence_to_estimated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter()

    class _FakeResponse:
        headers = {
            "anthropic-ratelimit-tokens-remaining": "40000",
            "anthropic-ratelimit-tokens-limit": "100000",
        }

    monkeypatch.setattr(
        adapter.client.messages.with_raw_response, "create", lambda **kwargs: _FakeResponse()
    )

    ok = adapter.refresh_usage()
    budget = adapter.get_available_budget()

    assert ok is True
    assert budget.confidence == UsageConfidence.ESTIMATED
    assert budget.remaining_percentage == 40.0


def test_openai_adapter_reports_unknown_before_refresh(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter()
    budget = adapter.get_available_budget()

    assert budget.confidence == UsageConfidence.UNKNOWN
    assert budget.source == "openai_rate_limit_headers"


def test_openai_adapter_execute_unit_is_not_implemented(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter
    from goldenboy.core.priorities import ExecutionUnit, Priority

    adapter = OpenAIAdapter()
    unit = ExecutionUnit("1", "Do the actual coding task", Priority.P0)

    with pytest.raises(NotImplementedError):
        adapter.execute_unit(unit)


def test_openai_adapter_refresh_updates_confidence_to_estimated(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter()

    class _FakeResponse:
        headers = {
            "x-ratelimit-remaining-tokens": "25000",
            "x-ratelimit-limit-tokens": "100000",
        }

    monkeypatch.setattr(
        adapter.client.chat.completions.with_raw_response, "create", lambda **kwargs: _FakeResponse()
    )

    ok = adapter.refresh_usage()
    budget = adapter.get_available_budget()

    assert ok is True
    assert budget.confidence == UsageConfidence.ESTIMATED
    assert budget.remaining_percentage == 25.0


def test_anthropic_adapter_refresh_failure_leaves_budget_unknown(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter()

    def _boom(**kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(adapter.client.messages.with_raw_response, "create", _boom)

    ok = adapter.refresh_usage()

    assert ok is False
    assert adapter.get_available_budget().confidence == UsageConfidence.UNKNOWN


def test_openai_adapter_refresh_failure_leaves_budget_unknown(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter()

    def _boom(**kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(adapter.client.chat.completions.with_raw_response, "create", _boom)

    ok = adapter.refresh_usage()

    assert ok is False
    assert adapter.get_available_budget().confidence == UsageConfidence.UNKNOWN


def test_anthropic_adapter_respects_safety_margin_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(safety_margin=10.0)
    budget = adapter.get_available_budget()

    assert budget.safety_margin == 10.0


# --- STALE confidence lifecycle -------------------------------------------
# The scenario section 4 of the task calls out explicitly:
#   process starts -> usage fetched -> long time passes -> usage becomes
#   stale -> the adapter must not keep reporting it as fresh (ESTIMATED).

def test_anthropic_adapter_confidence_ages_from_estimated_to_stale(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    clock = _FakeClock()
    adapter = AnthropicAdapter(config=GoldenBoyConfig(stale_after_seconds=60.0), clock=clock)
    monkeypatch.setattr(
        adapter.client.messages.with_raw_response, "create", lambda **kwargs: _fake_anthropic_response()
    )

    assert adapter.refresh_usage() is True
    assert adapter.get_available_budget().confidence == UsageConfidence.ESTIMATED

    clock.advance(59.0)
    assert adapter.get_available_budget().confidence == UsageConfidence.ESTIMATED, (
        "still within the freshness window"
    )

    clock.advance(2.0)  # total elapsed: 61s > 60s threshold
    assert adapter.get_available_budget().confidence == UsageConfidence.STALE


def test_anthropic_adapter_confidence_returns_to_estimated_after_a_fresh_refresh(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    clock = _FakeClock()
    adapter = AnthropicAdapter(config=GoldenBoyConfig(stale_after_seconds=60.0), clock=clock)
    monkeypatch.setattr(
        adapter.client.messages.with_raw_response, "create", lambda **kwargs: _fake_anthropic_response()
    )

    adapter.refresh_usage()
    clock.advance(100.0)
    assert adapter.get_available_budget().confidence == UsageConfidence.STALE

    adapter.refresh_usage()  # a fresh, successful refresh right now
    assert adapter.get_available_budget().confidence == UsageConfidence.ESTIMATED


def test_anthropic_adapter_failed_refresh_does_not_reset_the_staleness_clock(monkeypatch):
    """A failed refresh must not make old data look newer than it is --
    the existing reading keeps aging from its last *successful* refresh."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    clock = _FakeClock()
    adapter = AnthropicAdapter(config=GoldenBoyConfig(stale_after_seconds=60.0), clock=clock)
    monkeypatch.setattr(
        adapter.client.messages.with_raw_response, "create", lambda **kwargs: _fake_anthropic_response()
    )
    adapter.refresh_usage()
    clock.advance(100.0)  # already stale

    def _boom(**kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(adapter.client.messages.with_raw_response, "create", _boom)
    assert adapter.refresh_usage() is False

    assert adapter.get_available_budget().confidence == UsageConfidence.STALE


def test_openai_adapter_confidence_ages_from_estimated_to_stale(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    clock = _FakeClock()
    adapter = OpenAIAdapter(config=GoldenBoyConfig(stale_after_seconds=60.0), clock=clock)
    monkeypatch.setattr(
        adapter.client.chat.completions.with_raw_response, "create", lambda **kwargs: _fake_openai_response()
    )

    assert adapter.refresh_usage() is True
    assert adapter.get_available_budget().confidence == UsageConfidence.ESTIMATED

    clock.advance(61.0)
    assert adapter.get_available_budget().confidence == UsageConfidence.STALE


def test_openai_adapter_failed_refresh_does_not_reset_the_staleness_clock(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    clock = _FakeClock()
    adapter = OpenAIAdapter(config=GoldenBoyConfig(stale_after_seconds=60.0), clock=clock)
    monkeypatch.setattr(
        adapter.client.chat.completions.with_raw_response, "create", lambda **kwargs: _fake_openai_response()
    )
    adapter.refresh_usage()
    clock.advance(100.0)

    def _boom(**kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(adapter.client.chat.completions.with_raw_response, "create", _boom)
    assert adapter.refresh_usage() is False

    assert adapter.get_available_budget().confidence == UsageConfidence.STALE

import pytest

from goldenboy.adapters.mock import MockProvider
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.decision_engine import DecisionEngine
from goldenboy.core.task_types import DecisionAction


class _FixedBudgetProvider(MockProvider):
    """A MockProvider subclass that reports a chosen confidence instead of
    always EXACT, so UNKNOWN/STALE-specific behavior is directly testable."""

    def __init__(self, remaining_percentage: float, confidence: UsageConfidence, source: str = "fixture"):
        super().__init__(initial_percentage=remaining_percentage)
        self._confidence = confidence
        self._source = source

    def get_available_budget(self) -> Budget:
        return Budget(
            remaining_percentage=self._current_percentage,
            source=self._source,
            confidence=self._confidence,
        )


def test_decide_returns_a_well_formed_decision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=90.0)

    decision = engine.decide("Fix a bug in the login flow", provider)

    assert decision.task.task_type == "bug_fix"
    assert decision.usage.remaining_percentage == 90.0
    assert decision.action in {a.value for a in DecisionAction}
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.reason  # non-empty, real text


def test_safe_mode_with_no_progress_recommends_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=100.0)

    decision = engine.decide("Fix a typo in the README", provider)

    assert decision.risk.mode == "SAFE"
    assert decision.action == DecisionAction.RUN.value


def test_critical_mode_with_low_progress_recommends_stop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=2.0)  # below default 3.0% safety margin

    decision = engine.decide("Fix a bug", provider, progress=0.1)

    assert decision.risk.mode == "CRITICAL"
    assert decision.action == DecisionAction.STOP.value


def test_critical_mode_with_high_progress_recommends_finish(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=2.0)

    decision = engine.decide("Fix a bug", provider, progress=0.8)

    assert decision.risk.mode == "CRITICAL"
    assert decision.action == DecisionAction.FINISH.value


def test_near_done_progress_recommends_verify_even_when_safe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=100.0)

    decision = engine.decide("Refactor the estimator module and add tests", provider, progress=0.9)

    assert decision.action == DecisionAction.VERIFY.value


def test_limited_mode_recommends_reduce_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine(config=GoldenBoyConfig(max_budget_tokens=50))
    provider = MockProvider(initial_percentage=20.0)

    decision = engine.decide(
        "Implement a full OAuth login flow with refresh tokens, database migrations, "
        "and end-to-end tests across the entire application",
        provider,
    )

    assert decision.risk.mode == "LIMITED"
    assert decision.action == DecisionAction.REDUCE_SCOPE.value


def test_unknown_confidence_downgrades_safe_to_caution(tmp_path, monkeypatch):
    """The DecisionEngine-level conservative policy: a SAFE verdict backed
    by UNKNOWN confidence (e.g. a real adapter that never called
    refresh_usage()) is treated as CAUTION here -- without RiskEngine's own
    (intentionally neutral) UNKNOWN handling ever being touched."""
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = _FixedBudgetProvider(remaining_percentage=100.0, confidence=UsageConfidence.UNKNOWN)

    decision = engine.decide("Fix a typo in the README", provider)

    assert decision.usage.confidence == "UNKNOWN"
    assert decision.risk.mode == "CAUTION"
    assert "UNKNOWN_CONFIDENCE_DOWNGRADE" in decision.risk.reason_code


def test_exact_confidence_safe_is_not_downgraded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = _FixedBudgetProvider(remaining_percentage=100.0, confidence=UsageConfidence.EXACT)

    decision = engine.decide("Fix a typo in the README", provider)

    assert decision.risk.mode == "SAFE"


def test_stale_confidence_still_downgrades_via_risk_engine(tmp_path, monkeypatch):
    """RiskEngine's own STALE downgrade still applies unchanged underneath
    DecisionEngine -- this isn't reimplemented, just surfaced."""
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = _FixedBudgetProvider(remaining_percentage=100.0, confidence=UsageConfidence.STALE)

    decision = engine.decide("Fix a typo in the README", provider)

    assert decision.risk.mode == "CAUTION"


def test_low_confidence_recommends_ask_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    # A task with no classifiable keywords at all -> low classification
    # confidence; combined with UNKNOWN usage confidence, the blended
    # confidence should fall below the ask-user threshold.
    provider = _FixedBudgetProvider(remaining_percentage=100.0, confidence=UsageConfidence.UNKNOWN)

    decision = engine.decide("zzz qqq xyzzy plugh", provider)

    assert decision.action == DecisionAction.ASK_USER.value


def test_progress_out_of_range_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=100.0)

    with pytest.raises(ValueError):
        engine.decide("Fix a bug", provider, progress=1.5)

    with pytest.raises(ValueError):
        engine.decide("Fix a bug", provider, progress=-0.1)


def test_decision_is_json_serializable_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DecisionEngine()
    provider = MockProvider(initial_percentage=50.0)

    decision = engine.decide("Refactor the checkout module", provider)
    payload = decision.to_json()

    from goldenboy.protocol import GoldenBoyDecision

    restored = GoldenBoyDecision.from_json(payload)
    assert restored == decision

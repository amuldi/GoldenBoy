from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.heartbeat import check
from goldenboy.core.loop_detection import LoopDetector
from goldenboy.core.priorities import ExecutionUnit, Priority


def test_no_reasons_means_no_wake(tmp_path):
    result = check(state_dir=str(tmp_path))
    assert result.should_wake is False
    assert result.reasons == []


def test_pending_checkpoint_triggers_wake(tmp_path):
    cm = CheckpointManager(checkpoint_dir=str(tmp_path))
    cm.save("task", [ExecutionUnit("1", "x", Priority.P1, status="deferred")], "LIMITED")

    result = check(checkpoint_manager=cm, state_dir=str(tmp_path))
    assert result.should_wake is True
    assert any("checkpoint" in r.lower() for r in result.reasons)


def test_exhausted_budget_triggers_wake(tmp_path):
    budget = Budget(remaining_percentage=1.0, safety_margin=3.0, confidence=UsageConfidence.EXACT)
    result = check(budget=budget, state_dir=str(tmp_path))
    assert result.should_wake is True
    assert any("exhausted" in r.lower() for r in result.reasons)


def test_budget_change_triggers_wake(tmp_path):
    budget = Budget(remaining_percentage=50.0, confidence=UsageConfidence.EXACT)
    result = check(budget=budget, previous_budget_percentage=80.0, state_dir=str(tmp_path))
    assert result.should_wake is True
    assert any("changed" in r.lower() for r in result.reasons)


def test_unchanged_budget_does_not_trigger_wake(tmp_path):
    budget = Budget(remaining_percentage=80.0, safety_margin=3.0, confidence=UsageConfidence.EXACT)
    result = check(budget=budget, previous_budget_percentage=80.0, state_dir=str(tmp_path))
    assert result.should_wake is False


def test_loop_stop_triggers_wake(tmp_path):
    # Uses the same GoldenBoyConfig.loop_repeat_threshold default (3) that
    # `check()` itself reads -- heartbeat's cheap check has no way to know
    # a threshold a caller privately overrode when recording, only the
    # configured one.
    detector = LoopDetector(state_dir=str(tmp_path))
    for _ in range(3):
        detector.record("pytest", "a", "b")

    result = check(state_dir=str(tmp_path))
    assert result.should_wake is True
    assert any("loop" in r.lower() for r in result.reasons)


def test_never_imports_or_calls_any_network_or_llm_client():
    """Static guard: heartbeat.py must stay a pure local-file check, per its
    own docstring -- no network/LLM client imports."""
    import inspect

    from goldenboy.core import heartbeat

    source = inspect.getsource(heartbeat)
    for forbidden in ("requests", "httpx", "urllib", "socket", "anthropic", "openai"):
        assert forbidden not in source

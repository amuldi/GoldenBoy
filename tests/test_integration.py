from goldenboy.adapters.mock import MockProvider
from goldenboy.core.priorities import Priority
from goldenboy.integration import budget_aware_execution


def test_decorator_calls_the_real_function_when_budget_allows(tmp_path, monkeypatch):
    # A successful call now also appends a history event via the default
    # (cwd-relative) HistoryStore -- isolate cwd like every other test in
    # this file so that write can't land in the real project directory.
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=100.0)
    calls = []

    @budget_aware_execution(provider, "1", "Do real work", Priority.P1)
    def do_work():
        calls.append("ran")
        return "result"

    result = do_work()

    assert result == "result"
    assert calls == ["ran"]


def test_decorator_defers_without_calling_the_function_when_budget_forces_it(tmp_path, monkeypatch):
    # Below the (default 3.0%) safety margin -> Budget.is_exhausted() -> CRITICAL,
    # which defers every non-P0 unit before the decorator ever calls the function.
    # A defer writes a checkpoint via the default (cwd-relative) CheckpointManager,
    # so isolate cwd to keep this test from touching the real project's .goldenboy/.
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=2.0)
    calls = []

    @budget_aware_execution(provider, "1", "Do real work", Priority.P1)
    def do_work():
        calls.append("ran")
        return "result"

    result = do_work()

    assert result is None
    assert calls == []  # the real function must never run once deferred


def test_decorator_saves_a_checkpoint_on_defer(tmp_path, monkeypatch):
    from goldenboy.core.checkpoint import CheckpointManager

    # CheckpointManager defaults to "./.goldenboy" — isolate to a tmp cwd
    # so this test can't touch (or race with) the real project's checkpoint.
    monkeypatch.chdir(tmp_path)

    provider = MockProvider(initial_percentage=2.0)  # below safety margin -> CRITICAL -> deferred

    @budget_aware_execution(provider, "42", "Do real work", Priority.P1)
    def do_work():
        return "result"

    do_work()

    state = CheckpointManager().load()
    assert state is not None
    assert state["units"][0]["id"] == "42"

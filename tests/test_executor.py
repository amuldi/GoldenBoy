from goldenboy.adapters.mock import MockProvider
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import ExecutionMode


def get_test_plan():
    return [
        ExecutionUnit("1", "P0 Task", Priority.P0, estimated_cost=10.0),
        ExecutionUnit("2", "P1 Task", Priority.P1, estimated_cost=8.0),
        ExecutionUnit("3", "P2 Task", Priority.P2, estimated_cost=5.0),
        ExecutionUnit("4", "P3 Task", Priority.P3, estimated_cost=4.0),
        ExecutionUnit("5", "P4 Task", Priority.P4, estimated_cost=6.0),
    ]

def test_executor_safe_mode(tmp_path, monkeypatch):
    # AdaptiveExecutor's default CheckpointManager is cwd-relative (".goldenboy");
    # isolate cwd so these tests can't write into the real project directory.
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=100.0)
    executor = AdaptiveExecutor(provider)

    plan = get_test_plan()
    msg, final_plan = executor.execute("Safe Task", plan)

    # In safe mode, everything should complete if budget holds
    assert all(u.status == "completed" for u in final_plan)

def test_executor_limited_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=25.0)
    executor = AdaptiveExecutor(provider)

    plan = get_test_plan()
    # Total cost is 33. Budget is 25 (margin 3 -> usable 22). required(33) >
    # usable(22) -> LIMITED at the initial assessment.
    assert executor.assess(plan)[2] == ExecutionMode.LIMITED
    msg, final_plan = executor.execute("Limited Task", plan)

    completed = [u for u in final_plan if u.status == "completed"]

    assert len(completed) > 0
    # P3 and P4 should be deferred immediately by Limited mode adaptation
    assert any(u.priority == Priority.P4 and u.status == "deferred" for u in final_plan)

def test_executor_limited_mode_with_mid_execution_exhaustion(tmp_path, monkeypatch):
    """Initial assessment is LIMITED (not CRITICAL -- required(33) > usable(9)
    at budget=12), so LIMITED's plan adaptation only defers P3/P4 up front.
    P0 (cost 10) still fits the raw remaining_percentage (12) and completes,
    which then trips is_exhausted() (2 <= margin 3) and force-defers the
    rest mid-loop -- P1-P4 end up deferred by two different mechanisms."""
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=12.0)
    executor = AdaptiveExecutor(provider)

    plan = get_test_plan()
    assert executor.assess(plan)[2] == ExecutionMode.LIMITED
    msg, final_plan = executor.execute("Limited Task With Mid-Run Exhaustion", plan)

    completed = [u for u in final_plan if u.status == "completed"]
    deferred = [u for u in final_plan if u.status == "deferred"]
    assert completed == [plan[0]]  # only P0 fit the budget before it ran out
    assert len(deferred) == 4  # P1-P4

def test_executor_critical_mode(tmp_path, monkeypatch):
    """Budget already at/below the safety margin -> CRITICAL from the very
    first assessment (is_exhausted() short-circuits before LIMITED's
    required-vs-usable check), regardless of the plan's estimated cost."""
    monkeypatch.chdir(tmp_path)
    provider = MockProvider(initial_percentage=2.0)  # <= default 3.0% safety margin
    executor = AdaptiveExecutor(provider)

    plan = get_test_plan()
    assert executor.assess(plan)[2] == ExecutionMode.CRITICAL
    msg, final_plan = executor.execute("Critical Task", plan)

    # CRITICAL defers every non-P0 unit up front; P0 itself still can't
    # afford its cost (10) against an already-exhausted budget (2), so
    # nothing completes at all -- a stricter, more realistic outcome than
    # assuming P0 always gets through just because it's highest priority.
    assert all(u.status == "deferred" for u in final_plan)

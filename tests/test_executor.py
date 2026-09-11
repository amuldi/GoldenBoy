from goldenboy.core.priorities import Priority, ExecutionUnit
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.executor import AdaptiveExecutor

def get_test_plan():
    return [
        ExecutionUnit("1", "P0 Task", Priority.P0, estimated_cost=10.0),
        ExecutionUnit("2", "P1 Task", Priority.P1, estimated_cost=8.0),
        ExecutionUnit("3", "P2 Task", Priority.P2, estimated_cost=5.0),
        ExecutionUnit("4", "P3 Task", Priority.P3, estimated_cost=4.0),
        ExecutionUnit("5", "P4 Task", Priority.P4, estimated_cost=6.0),
    ]

def test_executor_safe_mode():
    provider = MockProvider(initial_percentage=100.0)
    executor = AdaptiveExecutor(provider)
    
    plan = get_test_plan()
    msg, final_plan = executor.execute("Safe Task", plan)
    
    # In safe mode, everything should complete if budget holds
    assert all(u.status == "completed" for u in final_plan)
    
def test_executor_limited_mode():
    provider = MockProvider(initial_percentage=25.0)
    executor = AdaptiveExecutor(provider)
    
    plan = get_test_plan()
    # Total cost is 33. Budget is 25. Usable is 22.
    # Risk should be LIMITED.
    msg, final_plan = executor.execute("Limited Task", plan)
    
    completed = [u for u in final_plan if u.status == "completed"]
    deferred = [u for u in final_plan if u.status == "deferred"]
    
    assert len(completed) > 0
    # P3 and P4 should be deferred immediately by Limited mode adaptation
    assert any(u.priority == Priority.P4 and u.status == "deferred" for u in final_plan)

def test_executor_critical_mode():
    # Budget barely above safety margin
    provider = MockProvider(initial_percentage=12.0)
    executor = AdaptiveExecutor(provider)
    
    plan = get_test_plan()
    msg, final_plan = executor.execute("Critical Task", plan)
    
    # Only P0 should be attempted in CRITICAL mode based on initial assessment
    # P0 costs 10, budget is 12 (usable 9). It will exceed usable and might exhaust.
    deferred = [u for u in final_plan if u.status == "deferred"]
    assert len(deferred) >= 4  # P1-P4 deferred

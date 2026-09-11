from functools import wraps
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.executor import AdaptiveExecutor

def budget_aware_execution(provider: ProviderAdapter, unit_id: str, description: str, priority: Priority):
    """
    A decorator that integrates Golden Boy's budget protection into any custom Python agent framework.
    It automatically estimates risk, records completion, or safely defers execution 
    if the budget is exhausted.
    
    Usage:
        @budget_aware_execution(openai_adapter, "1", "Refactor Dashboard", Priority.P2)
        def agent_refactor_code():
            # agent logic here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            executor = AdaptiveExecutor(provider)
            unit = ExecutionUnit(id=unit_id, description=description, priority=priority)
            
            # Formulate a mini-plan of just this unit to assess risk
            plan = [unit]
            
            # Adaptive Executor will check budget and assess if this unit should run
            budget = provider.get_available_budget()
            estimate = executor.estimator.estimate_plan(plan)
            mode = executor.risk_engine.assess(budget, estimate)
            
            adapted_plan = executor.adapt_plan(plan, mode)
            
            if adapted_plan[0].status == "deferred":
                print(f"Golden Boy [LIMIT REACHED]: Deferring {priority.name} task -> {description}")
                # In a real integration, we might want to save this directly
                executor.checkpointer.save(f"auto_{unit_id}", adapted_plan, mode.name)
                return None
            
            print(f"Golden Boy [{mode.name}]: Executing {priority.name} task -> {description}")
            try:
                # Execute actual agent code
                result = func(*args, **kwargs)
                unit.complete()
                return result
            except Exception as e:
                unit.defer()
                executor.checkpointer.save(f"auto_{unit_id}", [unit], mode.name)
                raise e
                
        return wrapper
    return decorator

import logging
from functools import wraps

from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.priorities import ExecutionUnit, Priority

logger = logging.getLogger("goldenboy.integration")


def budget_aware_execution(provider: ProviderAdapter, unit_id: str, description: str, priority: Priority):
    """
    A decorator that integrates Golden Boy's budget protection into any custom Python agent framework.
    It automatically estimates risk, records completion, or safely defers execution
    if the budget is exhausted.

    Unlike `AdaptiveExecutor.execute()`, this never asks the provider to
    perform the work — it always calls your own decorated function. That
    makes it the right integration point for real LLM-API providers
    (Anthropic/OpenAI adapters), which only know how to report usage, not
    execute coding tasks.

    Usage:
        @budget_aware_execution(anthropic_adapter, "1", "Refactor Dashboard", Priority.P2)
        def agent_refactor_code():
            # agent logic here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            executor = AdaptiveExecutor(provider)
            unit = ExecutionUnit(id=unit_id, description=description, priority=priority)

            # Assess this one unit exactly the way AdaptiveExecutor.execute()
            # would for a whole plan — same code path, so the two entry
            # points can't silently disagree on the same inputs.
            _budget, _estimate, mode = executor.assess([unit])
            adapted_plan = executor.adapt_plan([unit], mode)

            if adapted_plan[0].status == "deferred":
                logger.warning("[%s] Deferring %s task -> %s", mode.name, priority.name, description)
                executor.checkpointer.save(f"auto_{unit_id}", adapted_plan, mode.name, budget=_budget)
                return None

            logger.info("[%s] Executing %s task -> %s", mode.name, priority.name, description)
            try:
                # Execute actual agent code
                result = func(*args, **kwargs)
                unit.complete()
                return result
            except Exception as e:
                unit.defer()
                executor.checkpointer.save(f"auto_{unit_id}", [unit], mode.name, budget=_budget)
                raise e

        return wrapper
    return decorator

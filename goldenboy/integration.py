import logging
import time
from functools import wraps
from typing import Optional

from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.history import HistoryStore, TaskEvent
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.task_classifier import TaskClassifier

logger = logging.getLogger("goldenboy.integration")

# Module-level so it isn't rebuilt (recompiling its keyword patterns) on
# every decorated call -- the classifier itself is stateless.
_classifier = TaskClassifier()


def _record_history(
    history: HistoryStore, description: str, priority: Priority,
    budget, estimate, mode, outcome: str, started_at: float, provider: ProviderAdapter,
) -> None:
    """Best-effort: a history-log write must never be the reason a real
    task fails or its result changes, so any failure here is logged and
    swallowed rather than propagated."""
    try:
        classification = _classifier.classify(description)
        remaining_usage_end = None
        try:
            remaining_usage_end = provider.get_available_budget().remaining_percentage
        except Exception:  # pragma: no cover - defensive; a provider's own read must not break logging
            pass
        event = TaskEvent.create(
            task_text=description,
            task_type=classification.task_type.value,
            task_type_confidence=classification.confidence,
            priority=priority.name,
            estimated_cost_percentage=estimate.estimated_percentage,
            estimated_cost_confidence=estimate.confidence,
            usage_source=budget.source,
            usage_confidence=budget.confidence.value,
            remaining_usage_start=budget.remaining_percentage,
            remaining_usage_end=remaining_usage_end,
            decision_mode=mode.name,
            outcome=outcome,
            duration_seconds=time.monotonic() - started_at,
        )
        history.append(event)
    except Exception as e:  # pragma: no cover - defensive, see docstring above
        logger.warning("Could not record history event: %s", e)


def budget_aware_execution(
    provider: ProviderAdapter,
    unit_id: str,
    description: str,
    priority: Priority,
    history: Optional[HistoryStore] = None,
):
    """
    A decorator that integrates Golden Boy's budget protection into any custom Python agent framework.
    It automatically estimates risk, records completion, or safely defers execution
    if the budget is exhausted.

    Unlike `AdaptiveExecutor.execute()`, this never asks the provider to
    perform the work — it always calls your own decorated function. That
    makes it the right integration point for real LLM-API providers
    (Anthropic/OpenAI adapters), which only know how to report usage, not
    execute coding tasks.

    Every call also appends one `TaskEvent` to `history` (default: a
    `HistoryStore` at the current directory's `.goldenboy/history.jsonl`,
    same convention as the checkpoint file — see SECURITY.md) recording the
    decision and outcome, never the task's raw text. This is the data
    `goldenboy.analytics`/`goldenboy.replay` learn from; a fresh install
    starts with none, and everything downstream reports that honestly
    rather than assuming a baseline. Pass your own `HistoryStore` (e.g.
    pointed at a different directory) to redirect it, or a `HistoryStore`
    subclass whose `append` is a no-op to disable logging entirely.

    Usage:
        @budget_aware_execution(anthropic_adapter, "1", "Refactor Dashboard", Priority.P2)
        def agent_refactor_code():
            # agent logic here
            pass
    """
    history_store = history or HistoryStore()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            started_at = time.monotonic()
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
                _record_history(
                    history_store, description, priority, _budget, _estimate, mode,
                    "deferred", started_at, provider,
                )
                return None

            logger.info("[%s] Executing %s task -> %s", mode.name, priority.name, description)
            try:
                # Execute actual agent code
                result = func(*args, **kwargs)
                unit.complete()
                _record_history(
                    history_store, description, priority, _budget, _estimate, mode,
                    "completed", started_at, provider,
                )
                return result
            except Exception as e:
                unit.defer()
                executor.checkpointer.save(f"auto_{unit_id}", [unit], mode.name, budget=_budget)
                _record_history(
                    history_store, description, priority, _budget, _estimate, mode,
                    "failed", started_at, provider,
                )
                raise e

        return wrapper
    return decorator

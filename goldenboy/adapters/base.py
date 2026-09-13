from abc import ABC, abstractmethod

from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.priorities import ExecutionUnit


def confidence_for_age(age_seconds: float, stale_after_seconds: float) -> UsageConfidence:
    """ESTIMATED if a refreshed reading is still within its freshness
    window, STALE once it's aged past it. Shared by AnthropicAdapter and
    OpenAIAdapter (identical policy, not duplicated in each file) — callers
    are responsible for tracking their own last-refresh timestamp and
    clock, and for reporting UNKNOWN themselves when nothing has been
    refreshed yet (this function assumes a refresh happened)."""
    if age_seconds > stale_after_seconds:
        return UsageConfidence.STALE
    return UsageConfidence.ESTIMATED


class ProviderAdapter(ABC):
    """Abstract base class for all agent provider adapters.

    A ProviderAdapter's one required responsibility is reporting usage —
    normalizing whatever a given provider exposes into a `Budget`. Golden
    Boy does not execute coding work itself (see project charter: it is a
    budget/workload optimization layer, not a coding agent). Adapters that
    can genuinely execute a unit of work on the caller's behalf (chiefly
    `MockProvider`, for demos and tests) may override `execute_unit`; real
    LLM-API adapters generally cannot and should not pretend to.

    For real execution, wrap your own callable with
    `goldenboy.integration.budget_aware_execution`, which asks the adapter
    for a budget/mode decision and then calls *your* function — never the
    adapter — to do the actual work.
    """

    @abstractmethod
    def get_available_budget(self) -> Budget:
        """Fetch and normalize the current available usage/budget."""
        pass

    def execute_unit(self, unit: ExecutionUnit) -> bool:
        """
        Execute a single unit of work on the caller's behalf.

        Not supported by default: reporting usage and executing arbitrary
        coding work are different responsibilities, and most adapters only
        implement the former honestly. Override this only if the adapter
        genuinely can perform the unit (e.g. a mock/demo provider, or a
        future adapter wrapping a real task runner) — never by asking an
        LLM to "do" the task in a throwaway call and reporting success.
        """
        raise NotImplementedError(
            f"{type(self).__name__} reports usage but does not execute work. "
            "Use goldenboy.integration.budget_aware_execution to wrap your "
            "own function, or AdaptiveExecutor.assess(plan) to get a "
            "budget/mode decision without delegating execution."
        )

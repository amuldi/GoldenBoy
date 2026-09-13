from goldenboy.adapters.base import ProviderAdapter
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.priorities import ExecutionUnit


class MockProvider(ProviderAdapter):
    """A synthetic provider for testing and demos.

    Unlike the real adapters, MockProvider genuinely can "execute" a unit
    (it just deducts the unit's declared cost from a counter) — that's why
    it's the one adapter that overrides `execute_unit` for real, rather
    than delegating to the caller's own function via the
    `budget_aware_execution` decorator.
    """

    def __init__(self, initial_percentage: float = 100.0, cost_per_unit: float = 5.0):
        self._current_percentage = initial_percentage
        self.cost_per_unit = cost_per_unit

    def get_available_budget(self) -> Budget:
        return Budget(
            remaining_percentage=self._current_percentage,
            source="mock",
            confidence=UsageConfidence.EXACT,
        )

    def execute_unit(self, unit: ExecutionUnit) -> bool:
        """Simulate work and consume budget."""
        # Use explicitly provided unit cost or fallback to default mock cost
        cost = unit.estimated_cost if unit.estimated_cost > 0 else self.cost_per_unit
        
        # We check before spending to avoid going negative in mock
        if self._current_percentage < cost:
            self._current_percentage = 0.0
            return False
            
        self._current_percentage -= cost
        return True

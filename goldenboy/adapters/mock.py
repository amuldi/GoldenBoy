from typing import Optional

from goldenboy.adapters.base import GenerationResult, ProviderAdapter
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.priorities import ExecutionUnit


class MockProvider(ProviderAdapter):
    """A synthetic provider for testing and demos.

    Unlike the real adapters, MockProvider genuinely can "execute" a unit
    (it just deducts the unit's declared cost from a counter) — that's why
    it's the one adapter that overrides `execute_unit` for real, rather
    than delegating to the caller's own function via the
    `budget_aware_execution` decorator. It overrides `generate()` for the
    same reason: deterministic, no-network output that test suites and
    demos can rely on without mocking an SDK.
    """

    provider_name = "mock"

    def __init__(
        self,
        initial_percentage: float = 100.0,
        cost_per_unit: float = 5.0,
        model: str = "mock-model",
    ):
        self._current_percentage = initial_percentage
        self.cost_per_unit = cost_per_unit
        self.model: str = model

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

    def generate(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        reasoning_effort: Optional[str] = None,
    ) -> GenerationResult:
        """Deterministic, no-network stand-in for a real generation call.
        Output token count is `min(len(prompt.split()), max_output_tokens)`
        so tests can exercise the truncated/not-truncated path without
        randomness."""
        words = prompt.split()
        input_tokens = len(words)
        output_tokens = min(input_tokens, max_output_tokens)
        truncated = input_tokens > max_output_tokens
        text = " ".join(words[:output_tokens]) if truncated else f"mock response to: {prompt}"
        return GenerationResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason="max_tokens" if truncated else "end_turn",
            truncated=truncated,
            latency_ms=0.0,
            model=self.model,
            provider=self.provider_name,
        )

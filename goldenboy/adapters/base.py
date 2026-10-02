from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.model_registry import ModelRegistry, ModelSpec, get_default_registry
from goldenboy.core.priorities import ExecutionUnit


@dataclass(frozen=True)
class GenerationResult:
    """The normalized result of one real `ProviderAdapter.generate()` call.

    `truncated` is derived from the provider's own stop/finish reason
    (e.g. Anthropic's `"max_tokens"`, OpenAI's `"length"`) -- never
    guessed from output length, since providers can stop early for other
    reasons (tool use, a stop sequence) that aren't truncation.
    """

    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    truncated: bool
    latency_ms: float
    model: str
    provider: str


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

    #: Set by subclasses in __init__ to the model identifier they're
    #: configured to call (e.g. "claude-sonnet-4-5"). Used by `.spec`
    #: below to look up that model's `ModelSpec`. None on adapters (like
    #: MockProvider, by default) that aren't tied to one real model.
    model: Optional[str] = None
    #: Provider key used for `ModelRegistry` lookups ("anthropic"/"openai").
    #: Subclasses override this.
    provider_name: Optional[str] = None
    #: Optional injected registry (mainly for tests); falls back to the
    #: process-wide default registry when unset.
    _registry: Optional[ModelRegistry] = None

    @abstractmethod
    def get_available_budget(self) -> Budget:
        """Fetch and normalize the current available usage/budget."""
        pass

    @property
    def spec(self) -> Optional[ModelSpec]:
        """The `ModelSpec` for this adapter's configured model, looked up
        from the default `ModelRegistry` (or an injected one via
        `_registry`). None if the adapter isn't tied to a specific model,
        or if that model isn't in the registry -- this is the hook a
        future router (Stage 2) uses to make model-aware decisions; it
        deliberately never fabricates a spec for an unknown model."""
        registry = self._registry or get_default_registry()
        if self.provider_name is None or self.model is None:
            return None
        return registry.get(self.provider_name, self.model)

    def generate(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        reasoning_effort: Optional[str] = None,
    ) -> "GenerationResult":
        """Make one real generation call to the underlying model and
        return a normalized `GenerationResult`.

        Unlike `execute_unit` (which pretends to "do the task" and is
        deliberately unsupported by real provider adapters -- see the
        class docstring), `generate()` is an honest, narrow capability:
        it sends `prompt` to the configured model and reports back
        exactly what the provider returned (text + token usage + stop
        reason), nothing more. It does not loop, use tools, or interpret
        the response -- callers decide what to do with it.

        Not every adapter supports this (none did before this method was
        added); the default raises `NotImplementedError` so an adapter
        that doesn't override it fails loudly rather than silently.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement generate()."
        )

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

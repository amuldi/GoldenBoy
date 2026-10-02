"""Adaptive Model Router: a pure decision function that picks the cheapest
real `ModelSpec` (from `ModelRegistry`) satisfying a caller's capability and
quality requirements, under a caller-supplied USD budget.

This is NOT a replacement for `goldenboy.core.router.ModelRouter` (which
maps task complexity + budget risk to a provider-neutral `ModelTier` and is
left completely unmodified -- see that module's docstring). This router
answers a different question: given the *real* models in `ModelRegistry`
and their *real* per-1K pricing, which specific provider+model is the
cheapest one that actually qualifies for this task, and what happens if it
isn't available.

Budget note: `goldenboy.core.budget.Budget` is a *percentage* abstraction
(remaining_percentage / usable_percentage) with no USD field anywhere in
this codebase -- there is no existing Budget->USD conversion to reuse, and
inventing one here would be exactly the kind of fabricated figure this
project's conventions (see model_registry.py's docstring) forbid. This
router therefore takes `available_budget_usd` as a plain, caller-supplied
float: the caller (which has its own view of real-money budget, e.g. from
`goldenboy.core.spending`, its own billing data, or a hardcoded cap) is
responsible for turning its own budget notion into USD before calling in.

Pure decision function: `AdaptiveModelRouter.route()` has no side effects,
makes no network calls, and does not retry or execute anything -- it
returns a `RoutingPlan` for the caller to run through governance (the
Policy Engine, if wired up) and execution, consistent with this codebase's
"opt-in composition, no auto-wiring" convention.
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.model_registry import ModelRegistry, ModelSpec, get_default_registry

_VALID_STRATEGIES = {"cost_first", "quality_first", "adaptive"}

# Fixed, documented ordering -- mirrors ModelSpec.quality_class's own
# vocabulary ("fast" | "balanced" | "frontier"). Used only to compare
# "does this model meet the minimum quality requirement" and, for
# quality_first/adaptive, to prefer higher-quality models.
_QUALITY_RANK: Dict[str, int] = {"fast": 0, "balanced": 1, "frontier": 2}

# `adaptive` strategy's complexity cutoff: at or above this complexity
# label, adaptive behaves like quality_first (favor capability headroom
# over raw cost); below it, adaptive behaves like cost_first. A fixed,
# documented threshold -- not a tuned model.
_ADAPTIVE_HIGH_COMPLEXITY_LABELS = {"HIGH", "VERY_HIGH"}


class AdaptiveRouterError(GoldenBoyError):
    """The adaptive router config file names a strategy this module does
    not implement, or is otherwise malformed."""


@dataclass
class CapabilityRequirements:
    """Caller-supplied capability requirements for a task. These are
    booleans the caller determines however it likes (this stage does not
    attempt to auto-detect capability needs from a prompt) -- a model
    missing a `True` requirement here is never selected."""

    requires_tools: bool = False
    requires_vision: bool = False
    requires_structured_output: bool = False

    def is_satisfied_by(self, spec: ModelSpec) -> bool:
        if self.requires_tools and not spec.supports_tools:
            return False
        if self.requires_vision and not spec.supports_vision:
            return False
        if self.requires_structured_output and not spec.supports_structured_output:
            return False
        return True


@dataclass
class RoutingPlan:
    """The outcome of one `AdaptiveModelRouter.route()` call. `provider`/
    `model` are both `None` when no registered model satisfies the
    capability+quality requirements under budget -- callers must handle
    that case explicitly (deny / ask-user / widen budget via their own
    governance), never substitute a fallback that violates a constraint."""

    task_type: str
    complexity: str
    provider: Optional[str]
    model: Optional[str]
    reasoning: str
    input_budget_tokens: int
    output_budget_tokens: int
    estimated_cost: Optional[float]
    fallback_chain: List[Tuple[str, str]]
    capability_requirements_used: CapabilityRequirements
    fits_budget: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "task_type": self.task_type,
            "complexity": self.complexity,
            "provider": self.provider,
            "model": self.model,
            "reasoning": self.reasoning,
            "input_budget_tokens": self.input_budget_tokens,
            "output_budget_tokens": self.output_budget_tokens,
            "estimated_cost": self.estimated_cost,
            "fallback_chain": list(self.fallback_chain),
            "capability_requirements_used": {
                "requires_tools": self.capability_requirements_used.requires_tools,
                "requires_vision": self.capability_requirements_used.requires_vision,
                "requires_structured_output": self.capability_requirements_used.requires_structured_output,
            },
            "fits_budget": self.fits_budget,
        }


@dataclass
class AdaptiveRouterConfig:
    """`strategy`: one of `_VALID_STRATEGIES`. Config cascade mirrors
    `GoldenBoyConfig`'s file->default pattern (minus the env layer -- a
    single strategy name has no sensible per-field env override, same
    reasoning `RouterConfig` already documents for `tier_models`)."""

    strategy: str = "cost_first"

    def __post_init__(self) -> None:
        if self.strategy not in _VALID_STRATEGIES:
            raise AdaptiveRouterError(
                f"adaptive_router config strategy={self.strategy!r} is not "
                f"implemented (implemented strategies: {sorted(_VALID_STRATEGIES)})."
            )

    @classmethod
    def load(cls, config_path: str = ".goldenboy/adaptive_router.json") -> "AdaptiveRouterConfig":
        if not os.path.exists(config_path):
            return cls()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise AdaptiveRouterError(
                f"Could not parse adaptive router config at '{config_path}': {e}"
            ) from e
        except OSError as e:
            raise AdaptiveRouterError(
                f"Could not read adaptive router config at '{config_path}': {e}"
            ) from e
        if not isinstance(data, dict):
            raise AdaptiveRouterError(
                f"Adaptive router config at '{config_path}' must be a JSON object, "
                f"got {type(data).__name__}."
            )
        strategy = data.get("strategy", "cost_first")
        return cls(strategy=str(strategy))


def _estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000.0) * spec.input_cost_per_1k + (
        output_tokens / 1000.0
    ) * spec.output_cost_per_1k


def _qualifies_capability_and_quality(
    spec: ModelSpec, capability_requirements: CapabilityRequirements, min_quality: str
) -> bool:
    if not capability_requirements.is_satisfied_by(spec):
        return False
    return _QUALITY_RANK[spec.quality_class] >= _QUALITY_RANK[min_quality]


class AdaptiveModelRouter:
    """Picks a `ModelSpec` for a task from `ModelRegistry`. See module
    docstring for the budget/capability contract. `route()` is a pure
    function of its arguments plus the injected/default registry and
    config -- no state, no side effects."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        config: Optional[AdaptiveRouterConfig] = None,
    ):
        self.registry = registry or get_default_registry()
        self.config = config or AdaptiveRouterConfig.load()

    def route(
        self,
        task_type: str,
        complexity_label: str,
        capability_requirements: CapabilityRequirements,
        min_quality: str,
        available_budget_usd: float,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> RoutingPlan:
        if min_quality not in _QUALITY_RANK:
            raise AdaptiveRouterError(
                f"min_quality={min_quality!r} is not one of {sorted(_QUALITY_RANK)}."
            )

        qualifying: List[ModelSpec] = [
            spec
            for spec in self.registry.all().values()
            if _qualifies_capability_and_quality(spec, capability_requirements, min_quality)
        ]

        priced: List[Tuple[float, ModelSpec]] = [
            (_estimate_cost(spec, estimated_input_tokens, estimated_output_tokens), spec)
            for spec in qualifying
        ]

        within_budget = [(cost, spec) for cost, spec in priced if cost <= available_budget_usd]

        strategy = self.config.strategy
        selected_cost: Optional[float] = None
        selected_spec: Optional[ModelSpec] = None

        if within_budget:
            if strategy == "cost_first":
                selected_cost, selected_spec = min(
                    within_budget, key=lambda cs: (cs[0], cs[1].provider, cs[1].model)
                )
                reasoning = (
                    f"cost_first: cheapest model meeting required capabilities and "
                    f"minimum quality '{min_quality}' under ${available_budget_usd:.4f} budget."
                )
            elif strategy == "quality_first":
                selected_cost, selected_spec = max(
                    within_budget,
                    key=lambda cs: (_QUALITY_RANK[cs[1].quality_class], -cs[0]),
                )
                reasoning = (
                    f"quality_first: highest-quality model (tie-broken by cost) meeting "
                    f"required capabilities and minimum quality '{min_quality}' under "
                    f"${available_budget_usd:.4f} budget."
                )
            elif strategy == "adaptive":
                if complexity_label in _ADAPTIVE_HIGH_COMPLEXITY_LABELS:
                    selected_cost, selected_spec = max(
                        within_budget,
                        key=lambda cs: (_QUALITY_RANK[cs[1].quality_class], -cs[0]),
                    )
                    reasoning = (
                        f"adaptive: complexity '{complexity_label}' is high, so the "
                        f"highest-quality qualifying model under budget was chosen "
                        f"(tie-broken by cost)."
                    )
                else:
                    selected_cost, selected_spec = min(
                        within_budget, key=lambda cs: (cs[0], cs[1].provider, cs[1].model)
                    )
                    reasoning = (
                        f"adaptive: complexity '{complexity_label}' is not high, so the "
                        f"cheapest qualifying model under budget was chosen."
                    )
            else:  # pragma: no cover - AdaptiveRouterConfig.__post_init__ already guards this
                raise AdaptiveRouterError(f"strategy {strategy!r} is not implemented.")
        else:
            reasoning = (
                f"No registered model satisfies the required capabilities "
                f"({capability_requirements}) and minimum quality '{min_quality}' "
                f"within ${available_budget_usd:.4f} for an estimated "
                f"{estimated_input_tokens} input / {estimated_output_tokens} output tokens."
                if qualifying
                else
                f"No registered model satisfies the required capabilities "
                f"({capability_requirements}) and minimum quality '{min_quality}' at all."
            )

        # Fallback chain: every OTHER qualifying model (capability+quality,
        # regardless of whether it itself fits budget), cheapest first --
        # real registry entries, never invented ones. Excludes the
        # selected model itself.
        fallback_specs = [
            spec
            for cost, spec in sorted(priced, key=lambda cs: (cs[0], cs[1].provider, cs[1].model))
            if spec is not selected_spec
        ]
        fallback_chain = [(s.provider, s.model) for s in fallback_specs]

        return RoutingPlan(
            task_type=task_type,
            complexity=complexity_label,
            provider=selected_spec.provider if selected_spec else None,
            model=selected_spec.model if selected_spec else None,
            reasoning=reasoning,
            input_budget_tokens=estimated_input_tokens,
            output_budget_tokens=estimated_output_tokens,
            estimated_cost=selected_cost,
            fallback_chain=fallback_chain,
            capability_requirements_used=capability_requirements,
            fits_budget=selected_spec is not None,
        )

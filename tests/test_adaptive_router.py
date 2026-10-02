import pytest

from goldenboy.core.adaptive_router import (
    AdaptiveModelRouter,
    AdaptiveRouterConfig,
    AdaptiveRouterError,
    CapabilityRequirements,
)
from goldenboy.core.model_registry import ModelRegistry, ModelSpec


def _spec(provider, model, in_cost, out_cost, quality="balanced", tools=True, vision=True, structured=True):
    return ModelSpec(
        provider=provider,
        model=model,
        context_window=100_000,
        max_output_tokens=8_000,
        input_cost_per_1k=in_cost,
        output_cost_per_1k=out_cost,
        supports_reasoning_effort=False,
        supports_tools=tools,
        supports_vision=vision,
        supports_structured_output=structured,
        quality_class=quality,
        latency_class="medium",
    )


def _registry(*specs):
    return ModelRegistry(specs={f"{s.provider}:{s.model}": s for s in specs})


def test_picks_cheapest_qualifying_model():
    cheap = _spec("p", "cheap-model", 0.001, 0.002, quality="fast")
    mid = _spec("p", "mid-model", 0.01, 0.02, quality="balanced")
    expensive = _spec("p", "expensive-model", 0.1, 0.2, quality="frontier")
    registry = _registry(cheap, mid, expensive)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="cost_first"))

    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.provider == "p"
    assert plan.model == "cheap-model"
    assert plan.fits_budget is True


def test_never_picks_model_missing_required_capability():
    no_tools = _spec("p", "no-tools", 0.001, 0.001, tools=False)
    has_tools = _spec("p", "has-tools", 0.05, 0.05, tools=True)
    registry = _registry(no_tools, has_tools)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="cost_first"))

    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(requires_tools=True),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.model == "has-tools"
    assert "no-tools" not in [m for _, m in plan.fallback_chain]


def test_no_model_fits_budget_returns_honest_result():
    expensive = _spec("p", "expensive-model", 10.0, 10.0, quality="frontier")
    registry = _registry(expensive)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="cost_first"))

    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=0.01,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.provider is None
    assert plan.model is None
    assert plan.fits_budget is False
    assert plan.estimated_cost is None
    assert "no model fits" in plan.reasoning.lower() or "No registered model" in plan.reasoning


def test_never_exceeds_budget():
    cheap = _spec("p", "cheap", 0.001, 0.001)
    pricey = _spec("p", "pricey", 1.0, 1.0)
    registry = _registry(cheap, pricey)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="cost_first"))

    budget = 0.01
    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=budget,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.estimated_cost is not None
    assert plan.estimated_cost <= budget


def test_fallback_chain_ordered_by_cost():
    a = _spec("p", "a", 0.001, 0.001)
    b = _spec("p", "b", 0.01, 0.01)
    c = _spec("p", "c", 0.1, 0.1)
    registry = _registry(c, a, b)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="cost_first"))

    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.model == "a"
    assert plan.fallback_chain == [("p", "b"), ("p", "c")]


def test_quality_first_strategy_prefers_higher_quality_under_budget():
    fast = _spec("p", "fast-model", 0.001, 0.001, quality="fast")
    frontier = _spec("p", "frontier-model", 0.01, 0.01, quality="frontier")
    registry = _registry(fast, frontier)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="quality_first"))

    plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert plan.model == "frontier-model"


def test_adaptive_strategy_switches_on_complexity():
    fast = _spec("p", "fast-model", 0.001, 0.001, quality="fast")
    frontier = _spec("p", "frontier-model", 0.01, 0.01, quality="frontier")
    registry = _registry(fast, frontier)
    router = AdaptiveModelRouter(registry=registry, config=AdaptiveRouterConfig(strategy="adaptive"))

    low_plan = router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )
    high_plan = router.route(
        task_type="implementation",
        complexity_label="VERY_HIGH",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert low_plan.model == "fast-model"
    assert high_plan.model == "frontier-model"


def test_unimplemented_strategy_name_raises():
    with pytest.raises(AdaptiveRouterError):
        AdaptiveRouterConfig(strategy="made_up_strategy")


def test_config_driven_strategy_switching():
    cheap = _spec("p", "cheap", 0.001, 0.001, quality="fast")
    frontier = _spec("p", "frontier", 0.01, 0.01, quality="frontier")
    registry = _registry(cheap, frontier)

    cost_router = AdaptiveModelRouter(
        registry=registry, config=AdaptiveRouterConfig(strategy="cost_first")
    )
    quality_router = AdaptiveModelRouter(
        registry=registry, config=AdaptiveRouterConfig(strategy="quality_first")
    )

    cost_plan = cost_router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )
    quality_plan = quality_router.route(
        task_type="implementation",
        complexity_label="LOW",
        capability_requirements=CapabilityRequirements(),
        min_quality="fast",
        available_budget_usd=100.0,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
    )

    assert cost_plan.model == "cheap"
    assert quality_plan.model == "frontier"

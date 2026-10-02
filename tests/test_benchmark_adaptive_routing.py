from goldenboy.core.adaptive_router import CapabilityRequirements
from scripts.benchmark_adaptive_routing import (
    ADAPTIVE_ADAPTERS,
    ADAPTIVE_REGISTRY,
    BASELINE_ADAPTERS,
    BASELINE_REGISTRY,
    TASKS,
    ConditionResult,
    _projected_cost_usd,
    _run_condition,
)


def test_tasks_cover_at_least_three_tiers_and_two_task_type_categories():
    tiers = {t.tier for t in TASKS}
    task_types = {t.task_type for t in TASKS}
    assert {"simple", "medium", "complex"} <= tiers
    assert len(task_types) >= 2
    assert len(TASKS) >= 6


def test_baseline_registry_has_exactly_one_model_per_provider():
    specs = BASELINE_REGISTRY.all()
    providers = [s.provider for s in specs.values()]
    assert len(providers) == len(set(providers)) == len(BASELINE_ADAPTERS)


def test_adaptive_registry_has_exactly_one_model_per_provider():
    specs = ADAPTIVE_REGISTRY.all()
    providers = [s.provider for s in specs.values()]
    assert len(providers) == len(set(providers)) == len(ADAPTIVE_ADAPTERS)


def test_run_condition_executes_real_golden_boy_pipeline_with_mock_provider():
    task = TASKS[0]
    result = _run_condition(task, BASELINE_ADAPTERS, BASELINE_REGISTRY, strategy="quality_first")
    assert isinstance(result, ConditionResult)
    assert result.result.sufficient is True
    assert result.selected == "anthropic:claude-opus-4-1"
    assert result.total_tokens == result.input_tokens + result.output_tokens
    assert result.total_tokens > 0
    assert result.wall_clock_ms >= 0.0


def test_baseline_always_selects_the_one_registered_model():
    for task in TASKS:
        result = _run_condition(task, BASELINE_ADAPTERS, BASELINE_REGISTRY, strategy="quality_first")
        assert result.selected == "anthropic:claude-opus-4-1"


def test_adaptive_selects_a_qualifying_model_from_its_own_registry():
    valid = {f"{p}:{m}" for p, m in [("anthropic", "claude-haiku-4-5"), ("openai", "gpt-4o")]}
    for task in TASKS:
        result = _run_condition(task, ADAPTIVE_ADAPTERS, ADAPTIVE_REGISTRY, strategy="adaptive")
        assert result.selected in valid


def test_projected_cost_uses_real_registry_pricing_and_is_positive_for_nonempty_runs():
    task = TASKS[0]
    result = _run_condition(task, BASELINE_ADAPTERS, BASELINE_REGISTRY, strategy="quality_first")
    cost = _projected_cost_usd(result, BASELINE_REGISTRY)
    assert cost is not None
    assert cost > 0.0


def test_projected_cost_is_none_when_registry_has_no_matching_spec():
    task = TASKS[0]
    result = _run_condition(task, BASELINE_ADAPTERS, BASELINE_REGISTRY, strategy="quality_first")
    from goldenboy.core.model_registry import ModelRegistry

    empty_registry = ModelRegistry(specs={})
    assert _projected_cost_usd(result, empty_registry) is None


def test_capability_requirements_import_is_usable_directly():
    # Smoke test that the benchmark script's imports are wired correctly
    # for direct reuse outside of `main()`.
    reqs = CapabilityRequirements()
    assert reqs.requires_tools is False

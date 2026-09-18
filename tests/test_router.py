import json

import pytest

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.risk import ExecutionMode
from goldenboy.core.router import ModelRouter, ModelTier, RouterConfig


def test_simple_task_routes_to_cheap_tier():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("LOW", ExecutionMode.SAFE)
    assert decision.tier == ModelTier.CHEAP


def test_complex_task_routes_to_high_tier():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("HIGH", ExecutionMode.SAFE)
    assert decision.tier == ModelTier.HIGH


def test_critical_complexity_routes_to_highest_tier():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("VERY_HIGH", ExecutionMode.SAFE)
    assert decision.tier == ModelTier.HIGHEST


def test_budget_downgrades_a_complex_task():
    """A VERY_HIGH-complexity task under a LIMITED budget must not route to
    HIGHEST -- budget can only pull the tier down, never up."""
    router = ModelRouter(config=RouterConfig())
    decision = router.route("VERY_HIGH", ExecutionMode.LIMITED)
    assert decision.tier == ModelTier.CHEAP
    assert decision.complexity_tier == ModelTier.HIGHEST  # what complexity alone would have chosen


def test_critical_budget_forces_stop_regardless_of_complexity():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("LOW", ExecutionMode.CRITICAL)
    assert decision.tier == ModelTier.STOP


def test_safe_budget_never_upgrades_a_simple_task():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("LOW", ExecutionMode.SAFE)
    assert decision.tier == ModelTier.CHEAP  # not pushed up to HIGHEST just because budget allows it


def test_unmapped_tier_has_no_model_name_by_default():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("LOW", ExecutionMode.SAFE)
    assert decision.model_name is None


def test_configured_tier_model_is_returned():
    config = RouterConfig(tier_models={"cheap": "org/small-model-v1"})
    router = ModelRouter(config=config)
    decision = router.route("LOW", ExecutionMode.SAFE)
    assert decision.model_name == "org/small-model-v1"


def test_router_config_rejects_unknown_tier_name():
    with pytest.raises(GoldenBoyError):
        RouterConfig(tier_models={"not_a_real_tier": "x"})


def test_router_config_load_defaults_when_file_missing(tmp_path):
    config = RouterConfig.load(str(tmp_path / "missing.json"))
    assert config.tier_models == {}


def test_router_config_load_from_file(tmp_path):
    path = tmp_path / "router.json"
    path.write_text(json.dumps({"tier_models": {"standard": "org/mid-model"}}))
    config = RouterConfig.load(str(path))
    assert config.tier_models == {"standard": "org/mid-model"}


def test_router_config_malformed_json_raises(tmp_path):
    path = tmp_path / "router.json"
    path.write_text("{not valid")
    with pytest.raises(GoldenBoyError):
        RouterConfig.load(str(path))


def test_routing_decision_to_dict_is_json_serializable():
    router = ModelRouter(config=RouterConfig())
    decision = router.route("MEDIUM", ExecutionMode.CAUTION)
    json.dumps(decision.to_dict())  # must not raise

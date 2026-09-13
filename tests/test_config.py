import json

import pytest

from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.errors import ConfigError


def test_defaults_when_nothing_present(tmp_path):
    config = GoldenBoyConfig.load(str(tmp_path / "does_not_exist.json"))
    assert config == GoldenBoyConfig()


def test_json_file_overrides_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"safety_margin": 9.0, "caution_ratio": 0.4}))

    config = GoldenBoyConfig.load(str(path))

    assert config.safety_margin == 9.0
    assert config.caution_ratio == 0.4
    # Untouched keys keep their defaults.
    assert config.base_cost_per_unit == GoldenBoyConfig().base_cost_per_unit


def test_unknown_json_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"safety_margin": 9.0, "totally_made_up_key": 123}))

    config = GoldenBoyConfig.load(str(path))

    assert config.safety_margin == 9.0
    assert not hasattr(config, "totally_made_up_key")


def test_env_var_overrides_json_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"safety_margin": 9.0}))
    monkeypatch.setenv("GOLDENBOY_SAFETY_MARGIN", "1.5")

    config = GoldenBoyConfig.load(str(path))

    assert config.safety_margin == 1.5


def test_malformed_json_raises_configerror_not_raw_jsondecodeerror(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json")

    with pytest.raises(ConfigError, match="config.json"):
        GoldenBoyConfig.load(str(path))


def test_non_object_json_raises_configerror(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps([1, 2, 3]))

    with pytest.raises(ConfigError, match="JSON object"):
        GoldenBoyConfig.load(str(path))


def test_bad_env_var_type_raises_configerror(tmp_path, monkeypatch):
    monkeypatch.setenv("GOLDENBOY_SAFETY_MARGIN", "not-a-number")

    with pytest.raises(ConfigError, match="GOLDENBOY_SAFETY_MARGIN"):
        GoldenBoyConfig.load(str(tmp_path / "does_not_exist.json"))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"safety_margin": -0.01},
        {"safety_margin": 100.0},
        {"caution_ratio": -0.01},
        {"caution_ratio": 1.01},
        {"base_cost_per_unit": -1.0},
        {"max_budget_tokens": 0},
        {"max_budget_tokens": -100},
        {"stale_after_seconds": 0.0},
        {"stale_after_seconds": -1.0},
    ],
)
def test_out_of_range_values_raise_configerror(kwargs):
    with pytest.raises(ConfigError):
        GoldenBoyConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"safety_margin": 0.0},
        {"safety_margin": 99.99},
        {"caution_ratio": 0.0},
        {"caution_ratio": 1.0},
        {"base_cost_per_unit": 0.0},
        {"max_budget_tokens": 1},
        {"stale_after_seconds": 0.01},
    ],
)
def test_boundary_values_are_accepted(kwargs):
    GoldenBoyConfig(**kwargs)  # must not raise


def test_out_of_range_json_value_raises_configerror(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"caution_ratio": 5.0}))

    with pytest.raises(ConfigError, match="caution_ratio"):
        GoldenBoyConfig.load(str(path))

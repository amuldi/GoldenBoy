"""Tests for the Model Registry (goldenboy.core.model_registry):
- built-in defaults load correctly and are well-formed
- an unknown model lookup returns None, never a fabricated/guessed spec
- `.goldenboy/models.json` can override an existing entry and extend with
  a new one
- a broken override file raises ModelRegistryError instead of silently
  falling back to defaults
"""
import json

import pytest

from goldenboy.core.model_registry import (
    ModelRegistry,
    ModelRegistryError,
    ModelSpec,
    get_default_registry,
    reset_default_registry,
)


def test_defaults_load_and_contain_known_models():
    registry = ModelRegistry()
    spec = registry.get("anthropic", "claude-sonnet-4-5")
    assert spec is not None
    assert spec.provider == "anthropic"
    assert spec.context_window == 200_000
    assert spec.input_cost_per_1k > 0
    assert spec.output_cost_per_1k > 0


def test_unknown_model_lookup_returns_none_not_a_guess():
    registry = ModelRegistry()
    assert registry.get("anthropic", "claude-nonexistent-9000") is None
    assert registry.get("some-other-provider", "whatever") is None


def test_all_returns_every_registered_spec():
    registry = ModelRegistry()
    specs = registry.all()
    assert "anthropic:claude-sonnet-4-5" in specs
    assert "openai:gpt-4o" in specs
    assert all(isinstance(s, ModelSpec) for s in specs.values())


def test_model_spec_rejects_invalid_quality_class():
    with pytest.raises(ModelRegistryError):
        ModelSpec(
            provider="anthropic",
            model="x",
            context_window=1000,
            max_output_tokens=100,
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.001,
            supports_reasoning_effort=False,
            supports_tools=False,
            supports_vision=False,
            supports_structured_output=False,
            quality_class="super-ultra",
            latency_class="low",
        )


def test_model_spec_rejects_negative_cost():
    with pytest.raises(ModelRegistryError):
        ModelSpec(
            provider="anthropic",
            model="x",
            context_window=1000,
            max_output_tokens=100,
            input_cost_per_1k=-0.001,
            output_cost_per_1k=0.001,
            supports_reasoning_effort=False,
            supports_tools=False,
            supports_vision=False,
            supports_structured_output=False,
            quality_class="fast",
            latency_class="low",
        )


def test_load_with_missing_override_file_uses_defaults_only(tmp_path):
    missing = tmp_path / "models.json"
    registry = ModelRegistry.load(config_path=str(missing))
    assert registry.get("anthropic", "claude-sonnet-4-5") is not None


def test_load_override_extends_and_overrides(tmp_path):
    override_path = tmp_path / "models.json"
    override_path.write_text(
        json.dumps(
            [
                # Overrides an existing default entry's price.
                {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "context_window": 200_000,
                    "max_output_tokens": 64_000,
                    "input_cost_per_1k": 0.0099,
                    "output_cost_per_1k": 0.0499,
                    "supports_reasoning_effort": False,
                    "supports_tools": True,
                    "supports_vision": True,
                    "supports_structured_output": True,
                    "quality_class": "balanced",
                    "latency_class": "medium",
                },
                # A brand new entry.
                {
                    "provider": "custom",
                    "model": "custom-model-1",
                    "context_window": 32_000,
                    "max_output_tokens": 4_000,
                    "input_cost_per_1k": 0.002,
                    "output_cost_per_1k": 0.004,
                    "supports_reasoning_effort": False,
                    "supports_tools": False,
                    "supports_vision": False,
                    "supports_structured_output": False,
                    "quality_class": "fast",
                    "latency_class": "low",
                },
            ]
        )
    )

    registry = ModelRegistry.load(config_path=str(override_path))

    overridden = registry.get("anthropic", "claude-sonnet-4-5")
    assert overridden.input_cost_per_1k == 0.0099

    extended = registry.get("custom", "custom-model-1")
    assert extended is not None
    assert extended.context_window == 32_000

    # Other defaults are untouched.
    assert registry.get("openai", "gpt-4o") is not None


def test_load_rejects_non_list_json(tmp_path):
    override_path = tmp_path / "models.json"
    override_path.write_text(json.dumps({"not": "a list"}))
    with pytest.raises(ModelRegistryError):
        ModelRegistry.load(config_path=str(override_path))


def test_load_rejects_invalid_json(tmp_path):
    override_path = tmp_path / "models.json"
    override_path.write_text("{not valid json")
    with pytest.raises(ModelRegistryError):
        ModelRegistry.load(config_path=str(override_path))


def test_load_rejects_entry_missing_required_field(tmp_path):
    override_path = tmp_path / "models.json"
    override_path.write_text(
        json.dumps([{"provider": "anthropic", "model": "incomplete"}])
    )
    with pytest.raises(ModelRegistryError):
        ModelRegistry.load(config_path=str(override_path))


def test_get_default_registry_is_cached_and_resettable(tmp_path, monkeypatch):
    reset_default_registry()
    monkeypatch.chdir(tmp_path)
    first = get_default_registry()
    second = get_default_registry()
    assert first is second
    reset_default_registry()
    third = get_default_registry()
    assert third is not first

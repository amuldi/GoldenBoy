"""Guards the top-level `import goldenboy` surface: it must stay small and
deliberate, and must never require the optional anthropic/openai/tiktoken
extras just to import the package."""
import ast
import inspect

import goldenboy


def test_dunder_all_matches_documented_public_api():
    expected = {
        "__version__",
        "GoldenBoyConfig",
        "Budget",
        "UsageConfidence",
        "ExecutionMode",
        "RiskEngine",
        "Estimator",
        "TaskEstimate",
        "Priority",
        "ExecutionUnit",
        "AdaptiveExecutor",
        "budget_aware_execution",
        "ProviderAdapter",
        "MockProvider",
        "CheckpointManager",
        "GoldenBoyError",
        "ConfigError",
        "CheckpointError",
    }
    assert set(goldenboy.__all__) == expected
    for name in expected:
        assert hasattr(goldenboy, name), f"goldenboy.{name} is in __all__ but not actually importable"


def test_version_is_a_nonempty_string():
    assert isinstance(goldenboy.__version__, str)
    assert goldenboy.__version__


def test_provider_specific_adapters_are_not_exposed_at_top_level():
    """AnthropicAdapter/OpenAIAdapter require optional extras -- they must
    stay out of goldenboy/__init__.py so `import goldenboy` never needs them."""
    assert not hasattr(goldenboy, "AnthropicAdapter")
    assert not hasattr(goldenboy, "OpenAIAdapter")


def test_init_module_does_not_import_optional_provider_sdks():
    """Static check on goldenboy/__init__.py's own *import statements*: it
    must not import anthropic_adapter/openai_adapter (or anthropic/openai
    directly), since that would force those optional extras just to
    `import goldenboy`. Checked via ast rather than a plain substring match
    on the source so the docstring is free to mention them by name (as it
    does, explaining exactly why they're excluded) without tripping this.
    A process-level check (does sys.modules contain 'anthropic'?) would be
    order-dependent within a shared test session -- this isn't; the actual
    end-to-end guarantee is verified separately in a clean venv (see
    CONTRIBUTING.md / CI's default install step, which omits both extras).
    """
    tree = ast.parse(inspect.getsource(goldenboy))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for module_name in imported_modules:
        assert "anthropic" not in module_name, module_name
        assert "openai" not in module_name, module_name

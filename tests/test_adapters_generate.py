"""Tests for ProviderAdapter.generate() and the .spec hook:
- MockProvider.generate() is deterministic and exercises both the
  truncated and not-truncated paths, no network.
- AnthropicAdapter.generate() / OpenAIAdapter.generate() are tested
  against a mocked SDK client (same approach as
  test_adapters_usage_reporting.py's refresh_usage() tests) -- no real
  network calls.
- .spec resolves a known model via the default ModelRegistry and is
  None for an adapter not tied to a known model.
"""
import pytest

from goldenboy.adapters.base import GenerationResult
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.model_registry import ModelRegistry, ModelSpec

anthropic = pytest.importorskip("anthropic")
openai = pytest.importorskip("openai")


# --- MockProvider -----------------------------------------------------------

def test_mock_provider_generate_not_truncated():
    provider = MockProvider()
    result = provider.generate("hello world", max_output_tokens=100)

    assert isinstance(result, GenerationResult)
    assert result.truncated is False
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 2
    assert result.output_tokens == 2
    assert result.model == "mock-model"
    assert result.provider == "mock"
    assert result.latency_ms == 0.0


def test_mock_provider_generate_truncated():
    provider = MockProvider()
    result = provider.generate("one two three four five", max_output_tokens=2)

    assert result.truncated is True
    assert result.stop_reason == "max_tokens"
    assert result.output_tokens == 2
    assert result.input_tokens == 5


def test_mock_provider_spec_is_none_for_unregistered_model():
    provider = MockProvider()
    assert provider.spec is None  # "mock" provider isn't in the registry


# --- AnthropicAdapter ---------------------------------------------------

def test_anthropic_adapter_generate(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="claude-sonnet-4-5")

    class _TextBlock:
        type = "text"
        text = "hello from claude"

    class _Usage:
        input_tokens = 12
        output_tokens = 5

    class _FakeMessage:
        content = [_TextBlock()]
        usage = _Usage()
        stop_reason = "end_turn"

    monkeypatch.setattr(adapter.client.messages, "create", lambda **kwargs: _FakeMessage())

    result = adapter.generate("hi", max_output_tokens=50)

    assert result.text == "hello from claude"
    assert result.input_tokens == 12
    assert result.output_tokens == 5
    assert result.stop_reason == "end_turn"
    assert result.truncated is False
    assert result.model == "claude-sonnet-4-5"
    assert result.provider == "anthropic"
    assert result.latency_ms >= 0.0


def test_anthropic_adapter_generate_truncated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="claude-sonnet-4-5")

    class _TextBlock:
        type = "text"
        text = "cut off"

    class _Usage:
        input_tokens = 100
        output_tokens = 10

    class _FakeMessage:
        content = [_TextBlock()]
        usage = _Usage()
        stop_reason = "max_tokens"

    monkeypatch.setattr(adapter.client.messages, "create", lambda **kwargs: _FakeMessage())

    result = adapter.generate("hi", max_output_tokens=10)
    assert result.truncated is True


def test_anthropic_adapter_spec_resolves_from_registry(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="claude-sonnet-4-5")
    spec = adapter.spec

    assert spec is not None
    assert spec.provider == "anthropic"
    assert spec.model == "claude-sonnet-4-5"


def test_anthropic_adapter_spec_is_none_for_unknown_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="claude-totally-made-up")
    assert adapter.spec is None


def test_anthropic_adapter_spec_uses_injected_registry(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="custom-model")
    custom_spec = ModelSpec(
        provider="anthropic",
        model="custom-model",
        context_window=1234,
        max_output_tokens=56,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.002,
        supports_reasoning_effort=False,
        supports_tools=False,
        supports_vision=False,
        supports_structured_output=False,
        quality_class="fast",
        latency_class="low",
    )
    adapter._registry = ModelRegistry(specs={"anthropic:custom-model": custom_spec})

    assert adapter.spec is custom_spec


# --- OpenAIAdapter -------------------------------------------------------

def test_openai_adapter_generate(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(model="gpt-4o")

    class _Message:
        content = "hello from gpt"

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Usage:
        prompt_tokens = 20
        completion_tokens = 8

    class _FakeCompletion:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(
        adapter.client.chat.completions, "create", lambda **kwargs: _FakeCompletion()
    )

    result = adapter.generate("hi", max_output_tokens=50)

    assert result.text == "hello from gpt"
    assert result.input_tokens == 20
    assert result.output_tokens == 8
    assert result.stop_reason == "stop"
    assert result.truncated is False
    assert result.model == "gpt-4o"
    assert result.provider == "openai"


def test_openai_adapter_generate_truncated(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(model="gpt-4o")

    class _Message:
        content = "cut off"

    class _Choice:
        message = _Message()
        finish_reason = "length"

    class _Usage:
        prompt_tokens = 100
        completion_tokens = 10

    class _FakeCompletion:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(
        adapter.client.chat.completions, "create", lambda **kwargs: _FakeCompletion()
    )

    result = adapter.generate("hi", max_output_tokens=10)
    assert result.truncated is True


def test_openai_adapter_spec_resolves_from_registry(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(model="gpt-4o")
    spec = adapter.spec

    assert spec is not None
    assert spec.provider == "openai"
    assert spec.model == "gpt-4o"


def test_openai_adapter_reasoning_effort_logs_and_is_ignored(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    from goldenboy.adapters.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(model="gpt-4o")

    class _Message:
        content = "ok"

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Usage:
        prompt_tokens = 5
        completion_tokens = 1

    class _FakeCompletion:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(
        adapter.client.chat.completions, "create", lambda **kwargs: _FakeCompletion()
    )

    result = adapter.generate("hi", max_output_tokens=10, reasoning_effort="high")
    assert result.text == "ok"  # call still succeeds; reasoning_effort just ignored

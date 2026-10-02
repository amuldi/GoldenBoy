from goldenboy.adapters.base import GenerationResult
from goldenboy.core.estimator import Estimator
from goldenboy.core.model_registry import ModelSpec
from goldenboy.core.token_optimizer import (
    ContextChunk,
    TruncationCondition,
    classify_truncation,
    compute_output_budget_tokens,
    count_tokens,
    remove_duplicate_chunks,
    truncate_to_budget,
)


def _spec(max_output_tokens=8000):
    return ModelSpec(
        provider="p",
        model="m",
        context_window=100_000,
        max_output_tokens=max_output_tokens,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.001,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="balanced",
        latency_class="medium",
    )


def _result(truncated, stop_reason="stop"):
    return GenerationResult(
        text="hello",
        input_tokens=10,
        output_tokens=5,
        stop_reason=stop_reason,
        truncated=truncated,
        latency_ms=1.0,
        model="m",
        provider="p",
    )


def test_remove_duplicate_chunks_keeps_first_occurrence():
    chunks = [
        ContextChunk(key="a", text="aaa", priority=1.0),
        ContextChunk(key="b", text="bbb", priority=2.0),
        ContextChunk(key="a", text="aaa-dup", priority=5.0),
    ]
    result = remove_duplicate_chunks(chunks)
    assert [c.key for c in result] == ["a", "b"]
    assert result[0].text == "aaa"  # first occurrence kept, not the later dup


def test_truncate_to_budget_fits_exactly():
    # Each chunk is roughly 1 token under the fallback counter (4 chars/token).
    chunks = [ContextChunk(key=str(i), text="x" * 4, priority=float(i)) for i in range(5)]
    total_tokens = sum(c.tokens for c in chunks)
    result = truncate_to_budget(chunks, total_tokens)
    assert sum(c.tokens for c in result) <= total_tokens
    assert len(result) == 5


def test_truncate_to_budget_drops_lowest_priority_under_budget():
    chunks = [
        ContextChunk(key="low", text="x" * 400, priority=0.0),
        ContextChunk(key="high", text="x" * 400, priority=10.0),
    ]
    one_chunk_budget = chunks[1].tokens  # only room for one chunk
    result = truncate_to_budget(chunks, one_chunk_budget)
    kept_tokens = sum(c.tokens for c in result)
    assert kept_tokens <= one_chunk_budget
    assert [c.key for c in result] == ["high"]


def test_truncate_to_budget_preserves_original_order():
    chunks = [
        ContextChunk(key="first", text="x" * 4, priority=1.0),
        ContextChunk(key="second", text="x" * 4, priority=5.0),
        ContextChunk(key="third", text="x" * 4, priority=3.0),
    ]
    result = truncate_to_budget(chunks, budget_tokens=1_000_000)
    assert [c.key for c in result] == ["first", "second", "third"]


def test_truncate_to_budget_zero_budget_returns_empty():
    chunks = [ContextChunk(key="a", text="hello world", priority=1.0)]
    assert truncate_to_budget(chunks, 0) == []


def test_output_budget_respects_model_max_cap():
    spec = _spec(max_output_tokens=1000)
    budget_full_complexity = compute_output_budget_tokens(1.0, spec)
    budget_zero_complexity = compute_output_budget_tokens(0.0, spec)
    assert budget_full_complexity <= spec.max_output_tokens
    assert budget_zero_complexity <= spec.max_output_tokens
    assert budget_zero_complexity < budget_full_complexity
    assert budget_full_complexity == spec.max_output_tokens  # complexity=1.0 scales to the full max


def test_output_budget_clamps_out_of_range_complexity():
    spec = _spec(max_output_tokens=1000)
    assert compute_output_budget_tokens(-5.0, spec) == compute_output_budget_tokens(0.0, spec)
    assert compute_output_budget_tokens(5.0, spec) == compute_output_budget_tokens(1.0, spec)


def test_output_budget_floor_never_exceeds_small_model_max():
    spec = _spec(max_output_tokens=50)  # smaller than the usual floor
    assert compute_output_budget_tokens(0.0, spec) <= spec.max_output_tokens


def test_classify_truncation_detects_truncated_result():
    assert classify_truncation(_result(truncated=True, stop_reason="max_tokens")) == (
        TruncationCondition.TRUNCATED_OUTPUT_LIMIT
    )


def test_classify_truncation_detects_non_truncated_result():
    assert classify_truncation(_result(truncated=False, stop_reason="stop")) == (
        TruncationCondition.NOT_TRUNCATED
    )


def test_token_counting_consistent_with_estimator_fallback():
    # Without tiktoken, both this module and Estimator use the same
    # 4-chars/token fallback; with tiktoken, both use cl100k_base. Either
    # way the two should agree exactly for the same text.
    estimator = Estimator()
    text = "The quick brown fox jumps over the lazy dog." * 10
    assert count_tokens(text) == estimator._count_tokens(text)

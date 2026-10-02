"""Token Optimization: deterministic, non-LLM operations for shrinking
input context to a budget, sizing an output budget, and detecting
truncation. No network calls, no model calls -- every function here is a
pure transformation of its inputs.

Chunk representation: nothing in this codebase already models "a list of
context chunks/history" (`goldenboy.core.history.TaskEvent` is a single
settled outcome record, not a context chunk, and `estimator.py` works with
whole file contents, not chunks) -- so `ContextChunk` below is a new, small
representation rather than a parallel reinvention of an existing one.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List

from goldenboy.adapters.base import GenerationResult
from goldenboy.core.model_registry import ModelSpec

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

_ENCODING = tiktoken.get_encoding("cl100k_base") if HAS_TIKTOKEN else None


def count_tokens(text: str) -> int:
    """Same tiktoken-optional / word-count-fallback pattern as
    `goldenboy.core.estimator.Estimator._count_tokens`: a real `cl100k_base`
    tokenizer when `tiktoken` is installed, else ~4 characters/token (the
    standard rough English-text estimate, not a word-count heuristic)."""
    if HAS_TIKTOKEN and _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4) if text else 0


@dataclass(frozen=True)
class ContextChunk:
    """One unit of context/history a caller wants optimized before it goes
    into a prompt.

    `key` identifies exact duplicates (two chunks with the same `key` are
    the same piece of context seen twice, e.g. the same file re-included).
    `priority` is a caller-supplied or simple heuristic score -- higher
    means "keep this first." This module does not build or train any
    relevance model; a caller wanting a recency-based score can simply pass
    an increasing counter or timestamp as `priority`.
    """

    key: str
    text: str
    priority: float = 0.0

    @property
    def tokens(self) -> int:
        return count_tokens(self.text)


def remove_duplicate_chunks(chunks: List[ContextChunk]) -> List[ContextChunk]:
    """Drop exact-duplicate chunks (same `key`), keeping the first
    occurrence and original relative order of everything else."""
    seen = set()
    result: List[ContextChunk] = []
    for chunk in chunks:
        if chunk.key in seen:
            continue
        seen.add(chunk.key)
        result.append(chunk)
    return result


def truncate_to_budget(chunks: List[ContextChunk], budget_tokens: int) -> List[ContextChunk]:
    """Keep the highest-priority chunks that fit within `budget_tokens`,
    dropping the lowest-priority ones.

    Heuristic, not optimal: chunks are considered in descending-priority
    order (ties broken by original position, stable) and each is kept if
    it still fits in the remaining budget -- a greedy fill, not a knapsack
    solve. This is documented as a simple heuristic, not a tuned/ML
    relevance model. The returned list preserves the chunks' *original*
    relative order (not priority order), since reading order usually still
    matters to whatever consumes the result.
    """
    if budget_tokens <= 0:
        return []

    indexed = list(enumerate(chunks))
    by_priority = sorted(indexed, key=lambda pair: (-pair[1].priority, pair[0]))

    kept_indices = set()
    remaining = budget_tokens
    for idx, chunk in by_priority:
        cost = chunk.tokens
        if cost <= remaining:
            kept_indices.add(idx)
            remaining -= cost

    return [chunk for idx, chunk in indexed if idx in kept_indices]


# Output budget formula: scales linearly between a fixed floor and the
# model's real `max_output_tokens`, by complexity score in [0, 1].
# complexity=0.0 -> _OUTPUT_BUDGET_MIN_FRACTION of the model's max;
# complexity=1.0 -> the model's full max. This mirrors the *shape* of
# `estimator.py`'s own `_OUTPUT_MULTIPLIER_MIN/MAX` linear-scaling
# convention, but is a distinct, simpler formula (an absolute token count
# capped at a real model limit, not a multiplier on prompt tokens) -- a
# fixed, documented constant, not a figure tuned against any measured data.
_OUTPUT_BUDGET_MIN_FRACTION = 0.1
_OUTPUT_BUDGET_FLOOR_TOKENS = 256


def compute_output_budget_tokens(complexity_score: float, model_spec: ModelSpec) -> int:
    """`output_budget_tokens = max_output_tokens * (0.1 + 0.9 * complexity_score)`,
    floored at `_OUTPUT_BUDGET_FLOOR_TOKENS` (or the model's max, if that max
    is itself smaller than the floor) and always capped at
    `model_spec.max_output_tokens` -- this function never asks for more
    output than the model can actually produce.
    """
    clamped_score = min(1.0, max(0.0, complexity_score))
    raw = model_spec.max_output_tokens * (
        _OUTPUT_BUDGET_MIN_FRACTION + (1.0 - _OUTPUT_BUDGET_MIN_FRACTION) * clamped_score
    )
    floor = min(_OUTPUT_BUDGET_FLOOR_TOKENS, model_spec.max_output_tokens)
    return min(model_spec.max_output_tokens, max(floor, round(raw)))


class TruncationCondition(Enum):
    """A named classification of a `GenerationResult`'s truncation status,
    for Stage-3 escalation logic (not built in this stage) to react to.
    Deliberately just two values for now -- this stage only detects
    *whether* a result was cut off by the output-length limit, not finer
    distinctions (e.g. tool-use vs. stop-sequence truncation), since
    `GenerationResult.truncated` itself is already a single boolean derived
    from the provider's stop/finish reason (see `adapters/base.py`)."""

    NOT_TRUNCATED = "not_truncated"
    TRUNCATED_OUTPUT_LIMIT = "truncated_output_limit"


def classify_truncation(result: GenerationResult) -> TruncationCondition:
    """Classify one `GenerationResult`'s truncation status. Trusts
    `result.truncated` as-is (already derived honestly from the provider's
    own stop reason by the adapter -- see `GenerationResult`'s docstring);
    this function does not re-derive truncation from output length."""
    if result.truncated:
        return TruncationCondition.TRUNCATED_OUTPUT_LIMIT
    return TruncationCondition.NOT_TRUNCATED

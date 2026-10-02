"""Model Registry: real, verifiable per-model capability/pricing metadata
for the two providers Golden Boy has adapters for (Anthropic, OpenAI).

CRITICAL CONSTRAINT (see ARCHITECTURE_AUDIT.md / ROADMAP.md's "no
fabricated benchmark numbers or 'supports X' claims" principle, which this
registry is also bound by): every default entry below is a real,
currently-offered model as of this codebase's knowledge cutoff, with
pricing and context-window figures pulled from published provider
pricing/docs pages and noted with a `source` comment. Where a figure is
not confidently known, the model is left out entirely rather than
populating it with a plausible-looking guess. This registry is expected
to go stale as providers ship new models/prices — `.goldenboy/models.json`
(same defaults -> file -> env-free cascade used by `core.config`, minus
the env layer, since per-field env overrides make no sense for a model
*list*) lets callers correct or extend it without touching source.

This module only loads and looks up `ModelSpec`s. It intentionally does
not pick a model for a task or tier -- that's Stage 2's router job.
"""
import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from typing import Dict, Optional

from goldenboy.core.errors import GoldenBoyError

logger = logging.getLogger("goldenboy.model_registry")


class ModelRegistryError(GoldenBoyError):
    """The model registry override file (`.goldenboy/models.json`) is not
    valid JSON, or an entry in it is missing a required field."""


# Free-text by convention (not an Enum) -- mirrors how ModelTier is a
# routing-only vocabulary; quality_class/latency_class are open strings
# describing capability tier, not a Golden Boy routing decision.
_VALID_QUALITY_CLASSES = {"fast", "balanced", "frontier"}
_VALID_LATENCY_CLASSES = {"low", "medium", "high"}


@dataclass(frozen=True)
class ModelSpec:
    """Metadata for a single provider+model combination.

    All pricing is USD per 1,000 tokens, matching the providers' own
    published per-1K/per-1M pricing pages (divided down to per-1K here for
    a consistent unit regardless of provider).
    """

    provider: str
    model: str
    context_window: int
    max_output_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    supports_reasoning_effort: bool
    supports_tools: bool
    supports_vision: bool
    supports_structured_output: bool
    quality_class: str  # "fast" | "balanced" | "frontier"
    latency_class: str  # "low" | "medium" | "high"

    def __post_init__(self) -> None:
        if self.quality_class not in _VALID_QUALITY_CLASSES:
            raise ModelRegistryError(
                f"ModelSpec({self.provider}/{self.model}).quality_class="
                f"{self.quality_class!r} is not one of {sorted(_VALID_QUALITY_CLASSES)}."
            )
        if self.latency_class not in _VALID_LATENCY_CLASSES:
            raise ModelRegistryError(
                f"ModelSpec({self.provider}/{self.model}).latency_class="
                f"{self.latency_class!r} is not one of {sorted(_VALID_LATENCY_CLASSES)}."
            )
        if self.context_window <= 0:
            raise ModelRegistryError(
                f"ModelSpec({self.provider}/{self.model}).context_window must be > 0."
            )
        if self.max_output_tokens <= 0:
            raise ModelRegistryError(
                f"ModelSpec({self.provider}/{self.model}).max_output_tokens must be > 0."
            )
        if self.input_cost_per_1k < 0 or self.output_cost_per_1k < 0:
            raise ModelRegistryError(
                f"ModelSpec({self.provider}/{self.model}) costs must be >= 0."
            )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


# --- Built-in defaults -----------------------------------------------------
#
# Each entry's source is documented inline. Only models with pricing AND
# context-window figures I'm confident are accurate (published by
# Anthropic/OpenAI) are included. This list is deliberately short rather
# than exhaustive -- omission, not fabrication, is the fallback for any
# model/figure not confidently known.

_DEFAULT_MODELS = [
    # --- Anthropic ---
    # Source: Anthropic's published model pricing (docs.anthropic.com/en/docs/about-claude/pricing)
    # and model overview pages, for the Claude 4.x family current as of this
    # codebase's knowledge cutoff.
    ModelSpec(
        provider="anthropic",
        model="claude-opus-4-1",
        context_window=200_000,
        max_output_tokens=32_000,
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="frontier",
        latency_class="high",
    ),
    ModelSpec(
        provider="anthropic",
        model="claude-sonnet-4-5",
        context_window=200_000,
        max_output_tokens=64_000,
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="balanced",
        latency_class="medium",
    ),
    ModelSpec(
        provider="anthropic",
        model="claude-haiku-4-5",
        context_window=200_000,
        max_output_tokens=64_000,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.005,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="fast",
        latency_class="low",
    ),
    # --- OpenAI ---
    # Source: OpenAI's published API pricing page (openai.com/api/pricing)
    # for the GPT-4o and GPT-4o-mini models current as of this codebase's
    # knowledge cutoff. The GPT-5/o-series reasoning-model lineup is
    # evolving quickly enough that I'm not confident of exact current
    # prices/limits for every variant -- those are intentionally omitted
    # rather than guessed.
    ModelSpec(
        provider="openai",
        model="gpt-4o",
        context_window=128_000,
        max_output_tokens=16_384,
        input_cost_per_1k=0.0025,
        output_cost_per_1k=0.01,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="balanced",
        latency_class="medium",
    ),
    ModelSpec(
        provider="openai",
        model="gpt-4o-mini",
        context_window=128_000,
        max_output_tokens=16_384,
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
        supports_reasoning_effort=False,
        supports_tools=True,
        supports_vision=True,
        supports_structured_output=True,
        quality_class="fast",
        latency_class="low",
    ),
]

_SPEC_FIELD_NAMES = {f.name for f in fields(ModelSpec)}


def _key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


class ModelRegistry:
    """Looks up `ModelSpec`s by (provider, model).

    Loads the built-in defaults above, then merges in
    `.goldenboy/models.json` if present -- entries there with the same
    (provider, model) key override the built-in default; entries with a
    new key extend the registry. A missing file is not an error (same
    cascade convention as `GoldenBoyConfig`); a present-but-broken file
    raises `ModelRegistryError`.
    """

    def __init__(self, specs: Optional[Dict[str, ModelSpec]] = None):
        self._specs: Dict[str, ModelSpec] = specs if specs is not None else {
            _key(s.provider, s.model): s for s in _DEFAULT_MODELS
        }

    @classmethod
    def load(cls, config_path: str = ".goldenboy/models.json") -> "ModelRegistry":
        specs: Dict[str, ModelSpec] = {_key(s.provider, s.model): s for s in _DEFAULT_MODELS}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ModelRegistryError(
                    f"Could not parse model registry file at '{config_path}': {e}. "
                    "Fix the JSON syntax, or remove the file to use defaults."
                ) from e
            except OSError as e:
                raise ModelRegistryError(
                    f"Could not read model registry file at '{config_path}': {e}"
                ) from e

            if not isinstance(data, list):
                raise ModelRegistryError(
                    f"Model registry file at '{config_path}' must contain a JSON array "
                    f"of model entries, got {type(data).__name__}."
                )

            for i, entry in enumerate(data):
                if not isinstance(entry, dict):
                    raise ModelRegistryError(
                        f"Model registry entry #{i} in '{config_path}' must be a JSON "
                        f"object, got {type(entry).__name__}."
                    )
                missing = _SPEC_FIELD_NAMES - set(entry)
                if missing:
                    raise ModelRegistryError(
                        f"Model registry entry #{i} in '{config_path}' is missing "
                        f"required field(s): {', '.join(sorted(missing))}."
                    )
                unknown = set(entry) - _SPEC_FIELD_NAMES
                if unknown:
                    logger.warning(
                        "Ignoring unknown field(s) in model registry entry #%d of '%s': %s",
                        i, config_path, ", ".join(sorted(unknown)),
                    )
                try:
                    spec = ModelSpec(**{k: entry[k] for k in _SPEC_FIELD_NAMES})
                except TypeError as e:
                    raise ModelRegistryError(
                        f"Model registry entry #{i} in '{config_path}' is invalid: {e}"
                    ) from e
                specs[_key(spec.provider, spec.model)] = spec

        return cls(specs=specs)

    def get(self, provider: str, model: str) -> Optional[ModelSpec]:
        """Look up a `ModelSpec` by provider+model. Returns None for an
        unknown model -- callers must handle the "we don't have metadata
        for this model" case explicitly rather than receiving a guessed
        stand-in."""
        return self._specs.get(_key(provider, model))

    def all(self) -> Dict[str, ModelSpec]:
        """All registered specs, keyed by `"{provider}:{model}"`."""
        return dict(self._specs)


_default_registry: Optional[ModelRegistry] = None


def get_default_registry() -> ModelRegistry:
    """Process-wide cached registry, loaded via `ModelRegistry.load()`.
    Call `reset_default_registry()` after changing `.goldenboy/models.json`
    on disk mid-process (mainly useful in tests)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ModelRegistry.load()
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None

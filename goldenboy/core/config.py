"""Centralized, overridable configuration for Golden Boy's policy thresholds.

Every number that previously lived as a scattered default argument (safety
margin, the SAFE/CAUTION cutoff ratio, per-unit cost fallback, the token
budget used to turn raw token counts into a percentage) is defined here in
one place, with one override order:

    explicit constructor arg  >  GOLDENBOY_* environment variable
                              >  .goldenboy/config.json
                              >  built-in default

Nothing here changes default *behavior* from before this module existed.
What changes is that the numbers are now named, documented, range-checked,
and overridable without editing source.
"""
import json
import logging
import os
from dataclasses import dataclass, fields
from typing import Any, Dict, Optional

from goldenboy.core.errors import ConfigError

logger = logging.getLogger("goldenboy.config")

_ENV_PREFIX = "GOLDENBOY_"

# (field name) -> (min, max, min_inclusive, max_inclusive) — used by
# __post_init__ below. Documented here alongside the fields they guard so
# the valid range is never a surprise buried in validation code.
_RANGES = {
    # A safety margin >= 100 would make usable_percentage always 0 and
    # is_exhausted() always True regardless of remaining budget.
    "safety_margin": (0.0, 100.0, True, False),
    # caution_ratio splits SAFE from CAUTION as a fraction of usable
    # budget; outside [0, 1] the split stops meaning anything (e.g. >1
    # makes CAUTION effectively unreachable).
    "caution_ratio": (0.0, 1.0, True, True),
    # A negative fallback cost would make an under-specified plan look
    # cheaper than a fully-costed one, inverting the risk assessment.
    "base_cost_per_unit": (0.0, None, True, False),
    # Used as a divisor in Estimator; zero or negative breaks the
    # token-to-percentage conversion outright.
    "max_budget_tokens": (1, None, True, False),
    # How long a refreshed usage reading (e.g. from AnthropicAdapter /
    # OpenAIAdapter) stays ESTIMATED before aging into STALE. Must be > 0 --
    # zero would make every reading stale the instant it's read, which is
    # never useful and almost certainly a misconfiguration.
    "stale_after_seconds": (0.0, None, False, False),
}


def _validate(name: str, value) -> None:
    lo, hi, lo_incl, hi_incl = _RANGES[name]
    if lo is not None:
        ok = value >= lo if lo_incl else value > lo
        if not ok:
            raise ConfigError(
                f"GoldenBoyConfig.{name} = {value!r} is out of range "
                f"(must be {'>=' if lo_incl else '>'} {lo})."
            )
    if hi is not None:
        ok = value <= hi if hi_incl else value < hi
        if not ok:
            raise ConfigError(
                f"GoldenBoyConfig.{name} = {value!r} is out of range "
                f"(must be {'<=' if hi_incl else '<'} {hi})."
            )


@dataclass
class GoldenBoyConfig:
    """Policy thresholds used across the Budget/Risk/Estimator layers.

    Attributes:
        safety_margin: Percentage points reserved below the reported
            remaining budget before it is considered exhausted (Budget).
            Valid range: [0, 100).
        caution_ratio: If estimated_cost / usable_budget is below this
            ratio, RiskEngine reports SAFE; at or above it, CAUTION
            (before the LIMITED/CRITICAL checks that take priority).
            Valid range: [0, 1].
        base_cost_per_unit: Fallback cost (in budget percentage points)
            assigned to an ExecutionUnit that declares no explicit
            estimated_cost, used only when a whole plan is missing costs.
            Valid range: [0, inf).
        max_budget_tokens: The token count treated as "100% of budget" when
            Estimator converts a raw token estimate into a percentage.
            This is a rough normalization constant, not a real provider
            limit — providers with real limits (rate-limit headers, etc.)
            should report percentages directly instead of going through
            this constant. Valid range: [1, inf).
        stale_after_seconds: How long a refreshed usage reading is trusted
            as ESTIMATED before `UsageConfidence` ages it to STALE (see
            `AnthropicAdapter`/`OpenAIAdapter.get_available_budget()`).
            Valid range: (0, inf).

    Raises:
        ConfigError: if constructed with a value outside the ranges above.
    """

    safety_margin: float = 3.0
    caution_ratio: float = 0.5
    base_cost_per_unit: float = 2.0
    max_budget_tokens: int = 100_000
    stale_after_seconds: float = 300.0

    def __post_init__(self):
        for fld in fields(self):
            _validate(fld.name, getattr(self, fld.name))

    @classmethod
    def load(cls, config_path: str = ".goldenboy/config.json") -> "GoldenBoyConfig":
        """Build a config from defaults, then a JSON file, then env vars.

        A missing file is not an error — it simply falls back to defaults.
        A *present but broken* config file is a real user error and raises
        `ConfigError` (with the offending path and reason) rather than
        silently falling back to defaults, which could quietly undo a
        threshold someone intentionally tightened.
        """
        values: Dict[str, Any] = {}
        valid_keys = {fld.name for fld in fields(cls)}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_values = json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigError(
                    f"Could not parse config file at '{config_path}': {e}. "
                    "Fix the JSON syntax, or remove the file to use defaults."
                ) from e
            except OSError as e:
                raise ConfigError(f"Could not read config file at '{config_path}': {e}") from e

            if not isinstance(file_values, dict):
                raise ConfigError(
                    f"Config file at '{config_path}' must contain a JSON object, "
                    f"got {type(file_values).__name__}."
                )

            unknown = sorted(set(file_values) - valid_keys)
            if unknown:
                logger.warning(
                    "Ignoring unknown key(s) in '%s': %s (valid keys: %s)",
                    config_path, ", ".join(unknown), ", ".join(sorted(valid_keys)),
                )
            values.update({k: v for k, v in file_values.items() if k in valid_keys})

        for fld in fields(cls):
            env_name = _ENV_PREFIX + fld.name.upper()
            raw = os.getenv(env_name)
            if raw is None:
                continue
            # dataclasses.Field.type is typed as `type | str` (it can be a
            # string if annotations were ever stringified) -- the explicit
            # isinstance narrows that away for the type checker. Every
            # mypy version handles isinstance narrowing consistently, which
            # `fld.type in (int, float)` alone did not (see CHANGELOG: this
            # exact line failed under mypy 1.19.1, the version pip resolves
            # for Python 3.9, while passing under a newer local mypy).
            caster = fld.type if isinstance(fld.type, type) else None
            if caster in (int, float):
                try:
                    values[fld.name] = caster(raw)
                except ValueError as e:
                    raise ConfigError(
                        f"Environment variable {env_name}={raw!r} is not a valid "
                        f"{caster.__name__}."
                    ) from e
            else:
                values[fld.name] = raw

        return cls(**values)  # __post_init__ validates the merged result


_default_config: Optional[GoldenBoyConfig] = None


def get_default_config() -> GoldenBoyConfig:
    """Return a process-wide cached config loaded via GoldenBoyConfig.load().

    Cached so repeated construction of Budget/RiskEngine/Estimator objects
    (e.g. once per ExecutionUnit) doesn't re-read the config file each time.
    Call `reset_default_config()` after changing environment/config on disk
    mid-process (mainly useful in tests).
    """
    global _default_config
    if _default_config is None:
        _default_config = GoldenBoyConfig.load()
    return _default_config


def reset_default_config() -> None:
    global _default_config
    _default_config = None

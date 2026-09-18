"""Model Router: maps task complexity and budget risk to a *tier*, not a
vendor-specific model name.

Golden Boy does not ship real per-model pricing data (none is bundled, and
none is invented -- see ROADMAP.md's "no fabricated benchmark numbers or
'supports X' claims" principle) and does not hardcode a dependency on any
single AI provider. `ModelRouter.route()` therefore returns a tier from a
fixed, provider-neutral vocabulary (`ModelTier`); mapping a tier to an
actual model identifier (e.g. "claude-haiku-4-5" or "gpt-4o-mini") is an
opt-in, caller-supplied configuration (`RouterConfig.tier_models`,
`.goldenboy/router.json`) -- if it's not configured, `RoutingDecision.
model_name` is simply `None`, not a guessed default.

Two independent signals feed the tier, matching the project brief:
    - task complexity (`DecisionEngine`'s existing LOW/MEDIUM/HIGH/
      VERY_HIGH label, from `goldenboy.core.complexity` -- reused here
      rather than inventing a second complexity vocabulary)
    - budget risk (`RiskEngine`'s existing SAFE/CAUTION/LIMITED/CRITICAL
      `ExecutionMode` -- reused, not reimplemented)

The budget signal can only ever *downgrade* the tier complexity alone would
imply, never upgrade it -- a CRITICAL budget always caps at STOP/MINIMAL
regardless of how complex the task looks, and a SAFE budget never pushes a
LOW-complexity task up into a HIGHEST-tier model it doesn't need.
"""
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.risk import ExecutionMode


class RouterConfigError(GoldenBoyError):
    """The router config file (`.goldenboy/router.json`) is not valid JSON,
    or maps a tier name this module doesn't recognize."""


class ModelTier(Enum):
    STOP = "stop"        # Do not proceed -- budget cannot cover any model call.
    MINIMAL = "minimal"  # Smallest viable step only (e.g. a single targeted fix).
    CHEAP = "cheap"
    STANDARD = "standard"
    HIGH = "high"
    HIGHEST = "highest"


# Fixed ordering, cheapest/most-constrained first -- used to compute
# min(complexity_tier, budget_cap_tier) by index. Documented here, not
# scattered as magic comparisons.
_TIER_ORDER = [
    ModelTier.STOP, ModelTier.MINIMAL, ModelTier.CHEAP,
    ModelTier.STANDARD, ModelTier.HIGH, ModelTier.HIGHEST,
]

# Reuses `DecisionEngine`'s existing complexity_label vocabulary
# (goldenboy/core/decision_engine.py's `_complexity_label`) rather than
# inventing a second one.
_COMPLEXITY_TIER: Dict[str, ModelTier] = {
    "LOW": ModelTier.CHEAP,
    "MEDIUM": ModelTier.STANDARD,
    "HIGH": ModelTier.HIGH,
    "VERY_HIGH": ModelTier.HIGHEST,
}

# The budget/risk signal caps the tier at this ceiling -- it can only pull
# the final tier down, never push it up (see `ModelRouter.route`).
_MODE_CAP: Dict[ExecutionMode, ModelTier] = {
    ExecutionMode.SAFE: ModelTier.HIGHEST,
    ExecutionMode.CAUTION: ModelTier.HIGH,
    ExecutionMode.LIMITED: ModelTier.CHEAP,
    ExecutionMode.CRITICAL: ModelTier.STOP,
}


@dataclass
class RoutingDecision:
    tier: ModelTier
    complexity_label: str
    complexity_tier: ModelTier
    execution_mode: str
    budget_cap_tier: ModelTier
    reason: str
    model_name: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "tier": self.tier.value,
            "complexity_label": self.complexity_label,
            "complexity_tier": self.complexity_tier.value,
            "execution_mode": self.execution_mode,
            "budget_cap_tier": self.budget_cap_tier.value,
            "reason": self.reason,
            "model_name": self.model_name,
        }


@dataclass
class RouterConfig:
    """`tier_models`: an optional, caller-owned mapping from `ModelTier`
    value (e.g. `"cheap"`) to a real model identifier your integration
    actually uses. Empty by default -- Golden Boy has no opinion on which
    real model backs a tier until you tell it one."""

    tier_models: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_tiers = {t.value for t in ModelTier}
        unknown = sorted(set(self.tier_models) - valid_tiers)
        if unknown:
            raise RouterConfigError(
                f"router config has unknown tier name(s): {', '.join(unknown)} "
                f"(valid tiers: {', '.join(sorted(valid_tiers))})."
            )

    @classmethod
    def load(cls, config_path: str = ".goldenboy/router.json") -> "RouterConfig":
        if not os.path.exists(config_path):
            return cls()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise RouterConfigError(f"Could not parse router config at '{config_path}': {e}") from e
        except OSError as e:
            raise RouterConfigError(f"Could not read router config at '{config_path}': {e}") from e
        if not isinstance(data, dict):
            raise RouterConfigError(
                f"Router config at '{config_path}' must be a JSON object, got {type(data).__name__}."
            )
        tier_models = data.get("tier_models", {})
        if not isinstance(tier_models, dict):
            raise RouterConfigError(
                f"Router config's 'tier_models' must be a JSON object, got {type(tier_models).__name__}."
            )
        return cls(tier_models={str(k): str(v) for k, v in tier_models.items()})


class ModelRouter:
    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig.load()

    def route(self, complexity_label: str, mode: ExecutionMode) -> RoutingDecision:
        complexity_tier = _COMPLEXITY_TIER.get(complexity_label, ModelTier.STANDARD)
        budget_cap = _MODE_CAP[mode]

        if _TIER_ORDER.index(budget_cap) < _TIER_ORDER.index(complexity_tier):
            tier = budget_cap
            reason = (
                f"Complexity {complexity_label} alone would route to '{complexity_tier.value}', "
                f"but budget risk {mode.value} caps routing at '{budget_cap.value}'."
            )
        else:
            tier = complexity_tier
            reason = (
                f"Complexity {complexity_label} routes to '{tier.value}' "
                f"(budget risk {mode.value} does not constrain it further)."
            )

        return RoutingDecision(
            tier=tier,
            complexity_label=complexity_label,
            complexity_tier=complexity_tier,
            execution_mode=mode.value,
            budget_cap_tier=budget_cap,
            reason=reason,
            model_name=self.config.tier_models.get(tier.value),
        )

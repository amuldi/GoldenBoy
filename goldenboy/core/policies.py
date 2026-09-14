"""Baseline resource-allocation policies, for comparison against Golden
Boy's own risk engine in `goldenboy.replay`.

Every policy implements the same two-way decision (`PROCEED`/`STOP`) from
the same reconstructed pre-decision state (remaining budget + estimated
cost) so they can be compared fairly against identical historical inputs.
None of them peek at the event's recorded outcome -- that would be the
exact leakage the replay engine exists to avoid (see
`goldenboy.replay.engine`).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.estimator import TaskEstimate
from goldenboy.core.risk import ExecutionMode, RiskEngine


class PolicyDecision(Enum):
    PROCEED = "proceed"
    STOP = "stop"


@dataclass
class PolicyInput:
    """The reconstructed pre-decision state a policy is allowed to see --
    deliberately excludes anything about the actual outcome."""

    remaining_percentage: float
    estimated_cost_percentage: float
    usage_confidence: str = "UNKNOWN"


class Policy(ABC):
    name: str

    @abstractmethod
    def decide(self, state: PolicyInput) -> PolicyDecision:
        ...


class FixedThresholdPolicy(Policy):
    """Baseline A/B from the project brief: proceed as long as remaining
    budget is above a fixed percentage, regardless of task cost or
    confidence."""

    def __init__(self, threshold_percentage: float):
        self.threshold_percentage = threshold_percentage
        self.name = f"fixed_threshold_{threshold_percentage:g}pct"

    def decide(self, state: PolicyInput) -> PolicyDecision:
        return (
            PolicyDecision.PROCEED
            if state.remaining_percentage > self.threshold_percentage
            else PolicyDecision.STOP
        )


class ComplexityOnlyPolicy(Policy):
    """Ignores remaining budget entirely: proceeds unless the task's own
    estimated cost looks too large in absolute terms."""

    def __init__(self, max_cost_percentage: float = 50.0):
        self.max_cost_percentage = max_cost_percentage
        self.name = f"complexity_only_{max_cost_percentage:g}pct"

    def decide(self, state: PolicyInput) -> PolicyDecision:
        return (
            PolicyDecision.PROCEED
            if state.estimated_cost_percentage < self.max_cost_percentage
            else PolicyDecision.STOP
        )


class UsageOnlyPolicy(Policy):
    """Ignores task cost entirely: proceeds as long as *any* usable budget
    remains, using the same safety-margin definition Golden Boy's own
    Budget uses -- distinct from FixedThresholdPolicy in that the cutoff is
    the configured safety margin, not an arbitrary flat percentage."""

    def __init__(self, config: Optional[GoldenBoyConfig] = None):
        self.config = config or get_default_config()
        self.name = "usage_only_safety_margin"

    def decide(self, state: PolicyInput) -> PolicyDecision:
        budget = Budget(
            remaining_percentage=state.remaining_percentage,
            safety_margin=self.config.safety_margin,
        )
        return PolicyDecision.STOP if budget.is_exhausted() else PolicyDecision.PROCEED


class GoldenBoyPolicy(Policy):
    """Wraps the real, tested `RiskEngine` -- not a reimplementation.
    SAFE/CAUTION map to PROCEED; LIMITED/CRITICAL map to STOP, collapsing
    RiskEngine's 4-way mode into the 2-way vocabulary the other baselines
    share so they're comparable on identical footing."""

    def __init__(self, config: Optional[GoldenBoyConfig] = None):
        self.config = config or get_default_config()
        self.name = "golden_boy_risk_engine"
        self._engine = RiskEngine(config=self.config)

    def decide(self, state: PolicyInput) -> PolicyDecision:
        try:
            confidence = UsageConfidence(state.usage_confidence)
        except ValueError:
            confidence = UsageConfidence.UNKNOWN
        budget = Budget(
            remaining_percentage=state.remaining_percentage,
            safety_margin=self.config.safety_margin,
            confidence=confidence,
        )
        estimate = TaskEstimate(estimated_percentage=state.estimated_cost_percentage, confidence=1.0)
        mode = self._engine.assess(budget, estimate)
        return (
            PolicyDecision.PROCEED
            if mode in (ExecutionMode.SAFE, ExecutionMode.CAUTION)
            else PolicyDecision.STOP
        )


def default_baseline_policies(config: Optional[GoldenBoyConfig] = None) -> List[Policy]:
    """The standard comparison set used by `goldenboy replay` /
    `goldenboy.replay.engine.run_backtest` when no explicit policy list is
    given -- Baselines A-D plus Golden Boy's own engine, matching the
    project brief's comparison table."""
    cfg = config or get_default_config()
    return [
        FixedThresholdPolicy(threshold_percentage=15.0),
        FixedThresholdPolicy(threshold_percentage=20.0),
        ComplexityOnlyPolicy(),
        UsageOnlyPolicy(config=cfg),
        GoldenBoyPolicy(config=cfg),
    ]

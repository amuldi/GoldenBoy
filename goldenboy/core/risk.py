from enum import Enum
from typing import Optional

from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.estimator import TaskEstimate


class ExecutionMode(Enum):
    SAFE = "SAFE"           # Comfortably above estimated cost
    CAUTION = "CAUTION"     # Sufficient but has risk
    LIMITED = "LIMITED"     # Likely to exceed budget, reduce scope
    CRITICAL = "CRITICAL"   # Almost exhausted, stop safely

class RiskEngine:
    """Evaluates risk and determines the execution mode.

    The mode is decided by two independent checks, in order:
    1. Is the budget already exhausted (below its safety margin)? -> CRITICAL
    2. Does the estimated cost exceed what's usable at all? -> LIMITED
    Otherwise, SAFE/CAUTION is a ratio of estimated cost to usable budget,
    split at `caution_ratio` (config-driven, default 0.5 — i.e. a task
    estimated to consume half or more of the *usable* budget is CAUTION,
    not SAFE, even though it technically fits).
    """

    def __init__(self, config: Optional[GoldenBoyConfig] = None):
        self.config = config or get_default_config()

    def assess(self, budget: Budget, estimate: TaskEstimate) -> ExecutionMode:
        if budget.is_exhausted():
            return ExecutionMode.CRITICAL

        usable = budget.usable_percentage
        required = estimate.estimated_percentage

        if required > usable:
            return ExecutionMode.LIMITED

        ratio = required / usable if usable > 0 else 1.0
        mode = ExecutionMode.SAFE if ratio < self.config.caution_ratio else ExecutionMode.CAUTION

        # A SAFE verdict is an optimistic claim -- don't let it rest on data
        # that's known to be aged out. STALE means the adapter *had* real
        # data and it aged past `stale_after_seconds`; treat that as at most
        # CAUTION rather than reporting false confidence. UNKNOWN (the
        # Budget default, and the pre-refresh state of every real adapter)
        # is deliberately left alone here -- it's the long-standing neutral
        # default throughout the codebase, not a new "untrustworthy" signal,
        # and downgrading it would silently change behavior for every
        # caller that doesn't set confidence explicitly.
        if mode == ExecutionMode.SAFE and budget.confidence == UsageConfidence.STALE:
            return ExecutionMode.CAUTION

        return mode

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from goldenboy.core.config import get_default_config


class UsageConfidence(Enum):
    """How much to trust a Budget's remaining_percentage.

    Different usage sources have fundamentally different reliability:
    a provider that reports session/context usage directly can be EXACT,
    one that infers usage from something else (e.g. token counting, or an
    org-wide rate-limit bucket that doesn't map 1:1 to this session) is
    only ESTIMATED, and a source that hasn't reported anything yet, or
    whose last report has aged out, is STALE or UNKNOWN. Never render an
    ESTIMATED/STALE/UNKNOWN value as if it were EXACT.
    """
    EXACT = "EXACT"
    ESTIMATED = "ESTIMATED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass
class Budget:
    """Represents the available usage budget."""
    remaining_percentage: float  # 0.0 to 100.0
    total_allowed: Optional[float] = None
    safety_margin: float = field(default_factory=lambda: get_default_config().safety_margin)
    source: str = "unknown"  # e.g. "mock", "anthropic_rate_limit_headers", "claude_code_context"
    confidence: UsageConfidence = UsageConfidence.UNKNOWN

    @property
    def usable_percentage(self) -> float:
        """The actual budget available after reserving the safety margin."""
        return max(0.0, self.remaining_percentage - self.safety_margin)
        
    def is_safe(self, estimated_cost: float) -> bool:
        """Check if the estimated cost fits within the usable budget."""
        return self.usable_percentage >= estimated_cost
        
    def is_exhausted(self) -> bool:
        """Check if the budget is critically low (below safety margin)."""
        return self.remaining_percentage <= self.safety_margin


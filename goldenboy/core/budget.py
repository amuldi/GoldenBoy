from dataclasses import dataclass
from typing import Optional

@dataclass
class Budget:
    """Represents the available usage budget."""
    remaining_percentage: float  # 0.0 to 100.0
    total_allowed: Optional[float] = None
    safety_margin: float = 3.0  # Default 3% safety margin
    
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


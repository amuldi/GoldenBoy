from enum import IntEnum
from dataclasses import dataclass
from typing import List, Callable, Any

class Priority(IntEnum):
    P0 = 0  # Critical - Required for functionality
    P1 = 1  # Important - Required for good usable result
    P2 = 2  # Secondary - Useful improvements
    P3 = 3  # Polish - Refinements, animations
    P4 = 4  # Nice to have - Documentation, cleanup

@dataclass
class ExecutionUnit:
    """Represents a discrete unit of work within a larger task."""
    id: str
    description: str
    priority: Priority
    estimated_cost: float = 0.0
    status: str = "pending"  # pending, completed, deferred
    
    def complete(self):
        self.status = "completed"
        
    def defer(self):
        self.status = "deferred"

from enum import Enum
from goldenboy.core.budget import Budget
from goldenboy.core.estimator import TaskEstimate

class ExecutionMode(Enum):
    SAFE = "SAFE"           # Comfortably above estimated cost
    CAUTION = "CAUTION"     # Sufficient but has risk
    LIMITED = "LIMITED"     # Likely to exceed budget, reduce scope
    CRITICAL = "CRITICAL"   # Almost exhausted, stop safely

class RiskEngine:
    """Evaluates risk and determines the execution mode."""
    
    def assess(self, budget: Budget, estimate: TaskEstimate) -> ExecutionMode:
        if budget.is_exhausted():
            return ExecutionMode.CRITICAL
            
        usable = budget.usable_percentage
        required = estimate.estimated_percentage
        
        if required > usable:
            return ExecutionMode.LIMITED
            
        ratio = required / usable if usable > 0 else 1.0
        
        if ratio < 0.5:
            return ExecutionMode.SAFE
        else:
            return ExecutionMode.CAUTION

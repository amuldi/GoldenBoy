from dataclasses import dataclass
from typing import List
from goldenboy.core.priorities import ExecutionUnit

@dataclass
class TaskEstimate:
    estimated_percentage: float
    confidence: float  # 0.0 to 1.0

class Estimator:
    """Estimates the required budget for tasks."""
    
    def __init__(self, base_cost_per_unit: float = 2.0):
        self.base_cost_per_unit = base_cost_per_unit

    def estimate_task(self, prompt: str) -> TaskEstimate:
        """
        Estimate the overall task cost based on prompt complexity.
        This is a mock implementation that returns a baseline estimate.
        In a real adapter, this might involve analyzing AST, file size, etc.
        """
        # Very simple heuristic: length of prompt translates to complexity
        complexity = len(prompt.split())
        estimated = min(100.0, max(5.0, complexity * 0.5))
        confidence = 0.7  # Hardcoded for now
        
        return TaskEstimate(
            estimated_percentage=estimated,
            confidence=confidence
        )

    def estimate_plan(self, plan: List[ExecutionUnit]) -> TaskEstimate:
        """Estimate cost based on a concrete execution plan."""
        total_cost = sum(unit.estimated_cost for unit in plan if unit.status == "pending")
        if total_cost == 0:
            # Fallback if units have no explicit cost
            total_cost = len([u for u in plan if u.status == "pending"]) * self.base_cost_per_unit
            
        return TaskEstimate(
            estimated_percentage=total_cost,
            confidence=0.85
        )

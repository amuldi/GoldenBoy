import os
import glob
from dataclasses import dataclass
from typing import List
from goldenboy.core.priorities import ExecutionUnit

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

@dataclass
class TaskEstimate:
    estimated_percentage: float
    confidence: float  # 0.0 to 1.0

class Estimator:
    """Estimates the required budget for tasks by analyzing prompt tokens and repository size."""
    
    def __init__(self, base_cost_per_unit: float = 2.0, max_budget_tokens: int = 100000):
        self.base_cost_per_unit = base_cost_per_unit
        self.max_budget_tokens = max_budget_tokens
        if HAS_TIKTOKEN:
            self.encoding = tiktoken.get_encoding("cl100k_base")
            
    def _count_tokens(self, text: str) -> int:
        if HAS_TIKTOKEN:
            return len(self.encoding.encode(text))
        # Fallback to simple word count * 1.3
        return int(len(text.split()) * 1.3)
        
    def _estimate_codebase_context(self, directory: str = ".") -> int:
        """Estimates token footprint of the current codebase."""
        total_tokens = 0
        # Naive scan of python/js files up to a limit
        files = glob.glob(os.path.join(directory, "**", "*.py"), recursive=True)
        files += glob.glob(os.path.join(directory, "**", "*.ts"), recursive=True)
        files += glob.glob(os.path.join(directory, "**", "*.js"), recursive=True)
        
        for f in files[:50]:  # Limit scan depth
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    total_tokens += self._count_tokens(content)
            except Exception:
                pass
        return total_tokens

    def estimate_task(self, prompt: str) -> TaskEstimate:
        """
        Estimate the overall task cost based on prompt complexity and context.
        """
        prompt_tokens = self._count_tokens(prompt)
        context_tokens = self._estimate_codebase_context()
        
        # Assume an output multiplier based on prompt tokens and context mapping
        estimated_output_tokens = prompt_tokens * 3 
        total_estimated_tokens = context_tokens + prompt_tokens + estimated_output_tokens
        
        estimated_percentage = (total_estimated_tokens / self.max_budget_tokens) * 100.0
        estimated_percentage = min(100.0, max(5.0, estimated_percentage))
        
        confidence = 0.85 if HAS_TIKTOKEN else 0.50
        
        return TaskEstimate(
            estimated_percentage=estimated_percentage,
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
            confidence=0.90 if HAS_TIKTOKEN else 0.60
        )

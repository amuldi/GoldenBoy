from typing import List, Tuple
from goldenboy.core.budget import Budget
from goldenboy.core.estimator import TaskEstimate, Estimator
from goldenboy.core.risk import RiskEngine, ExecutionMode
from goldenboy.core.priorities import Priority, ExecutionUnit
from goldenboy.core.checkpoint import CheckpointManager

class AdaptiveExecutor:
    """The core engine that adapts execution based on budget constraints."""
    
    def __init__(self, provider_adapter):
        self.provider = provider_adapter
        self.estimator = Estimator()
        self.risk_engine = RiskEngine()
        self.checkpointer = CheckpointManager()
        
    def adapt_plan(self, plan: List[ExecutionUnit], mode: ExecutionMode) -> List[ExecutionUnit]:
        """Modifies the plan based on the execution mode."""
        if mode in (ExecutionMode.SAFE, ExecutionMode.CAUTION):
            # Try to execute everything, maybe with caution
            return plan
            
        elif mode == ExecutionMode.LIMITED:
            # Defer P3 and P4 tasks
            for unit in plan:
                if unit.priority in (Priority.P3, Priority.P4) and unit.status == "pending":
                    unit.defer()
            return plan
            
        elif mode == ExecutionMode.CRITICAL:
            # Defer everything except P0
            for unit in plan:
                if unit.priority != Priority.P0 and unit.status == "pending":
                    unit.defer()
            return plan
            
        return plan

    def execute(self, task_name: str, plan: List[ExecutionUnit]) -> Tuple[str, List[ExecutionUnit]]:
        """Executes the plan adaptively."""
        
        budget = self.provider.get_available_budget()
        estimate = self.estimator.estimate_plan(plan)
        mode = self.risk_engine.assess(budget, estimate)
        
        print(f"[{task_name}] Budget: {budget.remaining_percentage}% | Risk: {mode.name}")
        
        adapted_plan = self.adapt_plan(plan, mode)
        
        completed = []
        deferred = []
        
        for unit in adapted_plan:
            if unit.status == "deferred":
                deferred.append(unit)
                continue
                
            if unit.status == "completed":
                completed.append(unit)
                continue
                
            # Simulate execution via provider
            print(f"  -> Executing: [{unit.priority.name}] {unit.description}")
            success = self.provider.execute_unit(unit)
            
            if success:
                unit.complete()
                completed.append(unit)
            else:
                unit.defer()
                deferred.append(unit)
                
            # Re-evaluate budget after each unit
            current_budget = self.provider.get_available_budget()
            if current_budget.is_exhausted():
                print("  -> WARNING: Budget critically low. Triggering graceful stop.")
                # Defer remaining pending units
                for u in adapted_plan:
                    if u.status == "pending":
                        u.defer()
                        deferred.append(u)
                break
                
        # Save checkpoint if there are deferred items
        final_deferred = [u for u in adapted_plan if u.status == "deferred"]
        final_completed = [u for u in adapted_plan if u.status == "completed"]
        
        if final_deferred:
            print("  -> Saving checkpoint for deferred work.")
            self.checkpointer.save(task_name, adapted_plan, mode.name)
        else:
            self.checkpointer.clear()
            
        result_msg = f"Task '{task_name}' finished. Completed {len(final_completed)} units. Deferred {len(final_deferred)} units."
        return result_msg, adapted_plan

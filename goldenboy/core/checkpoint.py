import json
import os
from typing import List, Dict, Any
from goldenboy.core.priorities import Priority, ExecutionUnit

class CheckpointManager:
    """Manages saving and resuming task states to ensure recoverable work."""
    
    def __init__(self, checkpoint_dir: str = ".goldenboy"):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_file = os.path.join(self.checkpoint_dir, "checkpoint.json")
        
    def _ensure_dir(self):
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            
    def save(self, task_name: str, plan: List[ExecutionUnit], mode: str) -> None:
        """Save the current execution state."""
        self._ensure_dir()
        
        state = {
            "task_name": task_name,
            "mode": mode,
            "units": [
                {
                    "id": u.id,
                    "description": u.description,
                    "priority": u.priority.value,
                    "status": u.status,
                    "estimated_cost": u.estimated_cost
                }
                for u in plan
            ]
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(state, f, indent=2)
            
    def load(self) -> Dict[str, Any]:
        """Load the last saved checkpoint."""
        if not os.path.exists(self.checkpoint_file):
            return None
            
        with open(self.checkpoint_file, 'r') as f:
            state = json.load(f)
            
        # Reconstruct ExecutionUnits
        plan = []
        for u in state.get("units", []):
            plan.append(
                ExecutionUnit(
                    id=u["id"],
                    description=u["description"],
                    priority=Priority(u["priority"]),
                    status=u["status"],
                    estimated_cost=u.get("estimated_cost", 0.0)
                )
            )
            
        state["plan"] = plan
        return state
        
    def clear(self):
        """Remove the checkpoint file."""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

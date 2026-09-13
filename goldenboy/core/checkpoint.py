import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.budget import Budget
from goldenboy.core.errors import CheckpointError
from goldenboy.core.priorities import ExecutionUnit, Priority

# Bump when the on-disk schema changes in a way old readers can't handle.
# A checkpoint written by a newer, incompatible version raises CheckpointError
# rather than silently misreading fields that changed meaning.
CHECKPOINT_SCHEMA_VERSION = 1


def _next_recommended_action(plan: List[ExecutionUnit], mode: str) -> str:
    """A short, human-readable continuation hint — the whole point of a
    checkpoint is that the *next* session (or a human) can act on it
    without re-deriving state from the raw unit list."""
    deferred = [u for u in plan if u.status == "deferred"]
    if not deferred:
        return "No deferred work — nothing to resume."

    highest = min(deferred, key=lambda u: u.priority.value)
    return (
        f"Resume with 'goldenboy resume': {len(deferred)} unit(s) deferred "
        f"under {mode} mode. Highest-priority pending item: "
        f"[{highest.priority.name}] {highest.description}."
    )


class CheckpointManager:
    """Manages saving and resuming task states to ensure recoverable work."""

    def __init__(self, checkpoint_dir: str = ".goldenboy"):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_file = os.path.join(self.checkpoint_dir, "checkpoint.json")

    def _ensure_dir(self):
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

    def save(
        self,
        task_name: str,
        plan: List[ExecutionUnit],
        mode: str,
        budget: Optional[Budget] = None,
    ) -> None:
        """Save the current execution state.

        `budget` (if provided) is recorded as a snapshot so a later
        `status`/`resume` can show what the budget looked like *when this
        checkpoint was written*, distinct from the budget at resume time.
        """
        self._ensure_dir()

        state = {
            "version": CHECKPOINT_SCHEMA_VERSION,
            "task_name": task_name,
            "mode": mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "budget_snapshot": (
                {
                    "remaining_percentage": budget.remaining_percentage,
                    "source": budget.source,
                    "confidence": budget.confidence.value,
                }
                if budget is not None
                else None
            ),
            "next_recommended_action": _next_recommended_action(plan, mode),
            "units": [
                {
                    "id": u.id,
                    "description": u.description,
                    "priority": u.priority.value,
                    "status": u.status,
                    "estimated_cost": u.estimated_cost,
                }
                for u in plan
            ],
        }

        with open(self.checkpoint_file, "w") as f:
            json.dump(state, f, indent=2)

    def load(self) -> Optional[Dict[str, Any]]:
        """Load the last saved checkpoint.

        Returns None if no checkpoint exists. Raises `CheckpointError` (a
        clear message, not a raw traceback) if one exists but is corrupted,
        missing required fields, or was written by an incompatible future
        schema version — the caller (CLI) is expected to catch this and
        tell the user how to recover, e.g. by removing the file.
        """
        if not os.path.exists(self.checkpoint_file):
            return None

        try:
            with open(self.checkpoint_file, "r") as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            raise CheckpointError(
                f"Checkpoint file at '{self.checkpoint_file}' is corrupted ({e}). "
                "Remove it to start fresh — deferred work described in it will be lost."
            ) from e
        except OSError as e:
            raise CheckpointError(f"Could not read checkpoint file at '{self.checkpoint_file}': {e}") from e

        if not isinstance(state, dict):
            raise CheckpointError(
                f"Checkpoint file at '{self.checkpoint_file}' must contain a JSON object, "
                f"got {type(state).__name__}. Remove it to start fresh."
            )

        version = state.get("version", 1)  # checkpoints predating this field are version 1
        if version > CHECKPOINT_SCHEMA_VERSION:
            raise CheckpointError(
                f"Checkpoint file at '{self.checkpoint_file}' was written by a newer, "
                f"incompatible version (schema {version}, this Golden Boy understands "
                f"up to {CHECKPOINT_SCHEMA_VERSION}). Upgrade Golden Boy, or remove the "
                "file to start fresh."
            )

        if "task_name" not in state or "mode" not in state:
            raise CheckpointError(
                f"Checkpoint file at '{self.checkpoint_file}' is missing required fields "
                "('task_name'/'mode'). Remove it to start fresh."
            )

        try:
            plan = [
                ExecutionUnit(
                    id=u["id"],
                    description=u["description"],
                    priority=Priority(u["priority"]),
                    status=u["status"],
                    estimated_cost=u.get("estimated_cost", 0.0),
                )
                for u in state.get("units", [])
            ]
        except (KeyError, TypeError, ValueError) as e:
            raise CheckpointError(
                f"Checkpoint file at '{self.checkpoint_file}' has malformed unit data ({e}). "
                "Remove it to start fresh."
            ) from e

        state["plan"] = plan
        # Older checkpoints (written before these fields existed) won't have
        # them — default rather than making every caller guard.
        state.setdefault("created_at", None)
        state.setdefault("budget_snapshot", None)
        state.setdefault("next_recommended_action", None)
        return state

    def clear(self):
        """Remove the checkpoint file."""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

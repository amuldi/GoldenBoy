"""Heartbeat: a cheap, local-only "does anything need attention right now"
check -- explicitly NOT a background process, daemon, or server (see
ROADMAP.md's non-goals: "A database, a web dashboard, or an HTTP server
anywhere in this project"). Golden Boy does not sleep, loop, or schedule
anything itself; `check()` is a single, synchronous function a caller's own
scheduler (a cron job, an agent's own wait/poll loop, `goldenboy heartbeat`
run periodically by something outside this process) invokes when it wants
an answer, right now.

The check never calls an LLM or makes a network request -- it is pure
local-file inspection: is there a pending checkpoint with deferred work
(`CheckpointManager`), has the budget materially changed since the
caller's own last-known reading, is the budget exhausted, and has
`LoopDetector` recorded a stop-worthy repeat. Each is a cheap, synchronous
file read.

Experimental: the checks above are a reasonable starting set, not a
guarantee of catching everything worth waking up for -- see README.md's
honesty labeling for this module.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from goldenboy.core.budget import Budget
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig, get_default_config


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HeartbeatResult:
    should_wake: bool
    reasons: List[str] = field(default_factory=list)
    checked_at: str = field(default_factory=_utcnow_iso)


def _loop_stop_pending(state_dir: str, threshold: int) -> Optional[str]:
    """Cheap, synchronous read of `.goldenboy/loop_state.json` (no import
    of `LoopDetector` needed for a read-only check) -- returns a reason
    string if any tracked signature is at or above `threshold`, else
    `None`."""
    path = os.path.join(state_dir, "loop_state.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    entries = data.get("entries", {}) if isinstance(data, dict) else {}
    stuck = [e for e in entries.values() if isinstance(e, dict) and e.get("count", 0) >= threshold]
    if not stuck:
        return None
    tools = ", ".join(sorted({e.get("tool", "?") for e in stuck}))
    return f"Loop detection recorded {len(stuck)} signature(s) at/above threshold (tool(s): {tools})."


def check(
    checkpoint_manager: Optional[CheckpointManager] = None,
    budget: Optional[Budget] = None,
    previous_budget_percentage: Optional[float] = None,
    state_dir: str = ".goldenboy",
    config: Optional[GoldenBoyConfig] = None,
) -> HeartbeatResult:
    """Run every cheap local check and combine the results.

    All parameters are optional -- pass what you have. `budget` /
    `previous_budget_percentage` together detect a budget change since the
    caller's last known reading; passing only one (or neither) simply skips
    that specific check rather than raising.
    """
    cfg = config or get_default_config()
    reasons: List[str] = []

    cm = checkpoint_manager or CheckpointManager(checkpoint_dir=state_dir)
    if os.path.exists(cm.checkpoint_file):
        reasons.append("A checkpoint with possibly-deferred work exists (see 'goldenboy status').")

    if budget is not None:
        if budget.is_exhausted():
            reasons.append("Budget is exhausted (at or below its safety margin).")
        budget_changed = (
            previous_budget_percentage is not None
            and budget.remaining_percentage != previous_budget_percentage
        )
        if budget_changed:
            reasons.append(
                f"Budget changed since last check: {previous_budget_percentage:.1f}% -> "
                f"{budget.remaining_percentage:.1f}%."
            )

    loop_reason = _loop_stop_pending(state_dir, cfg.loop_repeat_threshold)
    if loop_reason:
        reasons.append(loop_reason)

    return HeartbeatResult(should_wake=bool(reasons), reasons=reasons)

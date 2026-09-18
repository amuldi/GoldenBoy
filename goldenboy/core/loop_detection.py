"""Loop Detection: stop an agent from retrying the same failing action
forever.

Golden Boy has no visibility into an agent's actual tool calls (it is not
an execution harness -- see ROADMAP.md's non-goals); this module gives the
calling agent a small, persistent counter it can check before each retry.
The caller builds a signature from whatever it already knows about the
attempt (tool name, a short argument summary, an error summary) and calls
`LoopDetector.record()`; once the same signature has been seen
`threshold` times (`GoldenBoyConfig.loop_repeat_threshold`, default 3),
`should_stop` becomes `True`.

State persists to `.goldenboy/loop_state.json` (a small mutable JSON
document, same convention as `CheckpointManager`'s checkpoint file, not an
append-only log -- this module's whole point is a *count*, not a history)
so counts survive across separate `goldenboy` CLI invocations within one
task/session; call `reset()` when starting a new task.

Only a hash of the composite signature is persisted, not the raw
tool/args/error text (same privacy convention as `HistoryStore.
TaskEvent.prompt_hash` -- see SECURITY.md) -- except the tool name itself,
kept in clear because it's useful for a human skimming the state file and
is not sensitive on its own.
"""
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.errors import GoldenBoyError

LOOP_STATE_SCHEMA_VERSION = 1


class LoopStateError(GoldenBoyError):
    """The loop-state file exists but is corrupted or malformed."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signature(tool: str, args_summary: str, error_summary: str) -> str:
    raw = f"{tool}|{args_summary}|{error_summary}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


@dataclass
class LoopEntry:
    signature: str
    tool: str
    count: int
    first_seen: str
    last_seen: str


@dataclass
class LoopCheckResult:
    signature: str
    tool: str
    count: int
    threshold: int
    should_stop: bool
    recommendation: str


class LoopDetector:
    def __init__(
        self,
        threshold: Optional[int] = None,
        state_dir: str = ".goldenboy",
        filename: str = "loop_state.json",
        config: Optional[GoldenBoyConfig] = None,
    ):
        cfg = config or get_default_config()
        self.threshold = threshold if threshold is not None else cfg.loop_repeat_threshold
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, filename)

    def _load(self) -> Dict[str, LoopEntry]:
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise LoopStateError(
                f"Loop-state file at '{self.state_file}' is corrupted ({e}). "
                "Remove it to reset loop-detection counts."
            ) from e
        except OSError as e:
            raise LoopStateError(f"Could not read loop-state file at '{self.state_file}': {e}") from e

        entries = data.get("entries", {}) if isinstance(data, dict) else {}
        result: Dict[str, LoopEntry] = {}
        for sig, raw in entries.items():
            try:
                result[sig] = LoopEntry(
                    signature=sig, tool=raw["tool"], count=raw["count"],
                    first_seen=raw["first_seen"], last_seen=raw["last_seen"],
                )
            except (KeyError, TypeError):
                continue  # one malformed entry doesn't invalidate the rest
        return result

    def _save(self, entries: Dict[str, LoopEntry]) -> None:
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        payload = {
            "schema_version": LOOP_STATE_SCHEMA_VERSION,
            "entries": {sig: asdict(e) for sig, e in entries.items()},
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def record(self, tool: str, args_summary: str = "", error_summary: str = "") -> LoopCheckResult:
        """Record one attempt and return whether it has now repeated at or
        above `threshold`. Call this once per attempt, right before (or
        instead of) retrying."""
        sig = _signature(tool, args_summary, error_summary)
        entries = self._load()
        now = _utcnow_iso()

        if sig in entries:
            entries[sig].count += 1
            entries[sig].last_seen = now
        else:
            entries[sig] = LoopEntry(signature=sig, tool=tool, count=1, first_seen=now, last_seen=now)

        self._save(entries)

        count = entries[sig].count
        should_stop = count >= self.threshold
        if should_stop:
            recommendation = (
                f"Stop retrying: the same (tool, args, error) signature has repeated {count} "
                f"time(s), at or above the threshold of {self.threshold}. Save state and report "
                "the failure rather than retrying again."
            )
        else:
            recommendation = f"Continue: {count} of {self.threshold} allowed repeat(s) so far."

        return LoopCheckResult(
            signature=sig, tool=tool, count=count, threshold=self.threshold,
            should_stop=should_stop, recommendation=recommendation,
        )

    def status(self) -> Dict[str, LoopEntry]:
        """All currently tracked signatures -- for inspection/reporting."""
        return self._load()

    def reset(self) -> None:
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

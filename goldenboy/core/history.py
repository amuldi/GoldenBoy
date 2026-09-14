"""Local, append-only event log Golden Boy learns from over time.

Every event is one JSON line appended to `.goldenboy/history.jsonl` (same
directory and gitignore convention as `CheckpointManager`'s checkpoint
file -- see SECURITY.md). This is the *only* data source the analytics
(`goldenboy.analytics`) and replay (`goldenboy.replay`) subsystems use:
there is no bundled dataset and no network call. On a fresh install the
file doesn't exist and every downstream report says so honestly (N rows =
0), rather than fabricating a baseline.

Privacy (see SECURITY.md / project rule "avoid storing sensitive user
content"): an event never stores the task's raw prompt text. Only its
length and a truncated SHA-256 hash are kept (enough to detect exact
repeats without being able to recover the original text).
"""
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.errors import GoldenBoyError

HISTORY_SCHEMA_VERSION = 1


class HistoryError(GoldenBoyError):
    """The history log could not be read (I/O failure) -- distinct from a
    single malformed line, which `load_events` reports as a count rather
    than raising, since one bad line shouldn't hide every valid one."""


def _hash_prompt(task_text: str) -> str:
    return hashlib.sha256(task_text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskEvent:
    """One recorded task outcome. Every field here is something Golden Boy
    itself actually measured at execution time (see `AdaptiveExecutor` /
    `budget_aware_execution`) -- fields the current architecture has no way
    to observe (tool-call counts, file/line diffs, test results) are simply
    not included rather than populated with an invented value. A future
    version may add them once there's a real, wired-up source for them."""

    schema_version: int
    timestamp: str
    task_type: str
    task_type_confidence: float
    prompt_length: int
    prompt_hash: str
    priority: Optional[str]
    estimated_cost_percentage: float
    estimated_cost_confidence: float
    usage_source: str
    usage_confidence: str
    remaining_usage_start: float
    remaining_usage_end: Optional[float]
    decision_mode: str
    outcome: str  # "completed" | "deferred" | "failed"
    duration_seconds: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task_text: str,
        task_type: str,
        task_type_confidence: float,
        priority: Optional[str],
        estimated_cost_percentage: float,
        estimated_cost_confidence: float,
        usage_source: str,
        usage_confidence: str,
        remaining_usage_start: float,
        decision_mode: str,
        outcome: str,
        remaining_usage_end: Optional[float] = None,
        duration_seconds: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "TaskEvent":
        return cls(
            schema_version=HISTORY_SCHEMA_VERSION,
            timestamp=_utcnow_iso(),
            task_type=task_type,
            task_type_confidence=task_type_confidence,
            prompt_length=len(task_text),
            prompt_hash=_hash_prompt(task_text),
            priority=priority,
            estimated_cost_percentage=estimated_cost_percentage,
            estimated_cost_confidence=estimated_cost_confidence,
            usage_source=usage_source,
            usage_confidence=usage_confidence,
            remaining_usage_start=remaining_usage_start,
            remaining_usage_end=remaining_usage_end,
            decision_mode=decision_mode,
            outcome=outcome,
            duration_seconds=duration_seconds,
            extra=extra or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskEvent":
        required = (
            "schema_version", "timestamp", "task_type", "task_type_confidence",
            "prompt_length", "prompt_hash", "estimated_cost_percentage",
            "estimated_cost_confidence", "usage_source", "usage_confidence",
            "remaining_usage_start", "decision_mode", "outcome",
        )
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"missing field(s): {', '.join(missing)}")
        return cls(
            schema_version=data["schema_version"],
            timestamp=data["timestamp"],
            task_type=data["task_type"],
            task_type_confidence=data["task_type_confidence"],
            prompt_length=data["prompt_length"],
            prompt_hash=data["prompt_hash"],
            priority=data.get("priority"),
            estimated_cost_percentage=data["estimated_cost_percentage"],
            estimated_cost_confidence=data["estimated_cost_confidence"],
            usage_source=data["usage_source"],
            usage_confidence=data["usage_confidence"],
            remaining_usage_start=data["remaining_usage_start"],
            remaining_usage_end=data.get("remaining_usage_end"),
            decision_mode=data["decision_mode"],
            outcome=data["outcome"],
            duration_seconds=data.get("duration_seconds"),
            extra=data.get("extra", {}),
        )


class HistoryStore:
    """Append-only JSONL log. `append()` never raises on a write it can't
    make land on disk cleanly except a genuine I/O failure (`HistoryError`)
    -- it must never be the reason a real task fails. `load_events()` is
    tolerant of individual corrupted lines (skips and counts them, see
    `LoadResult`) so one bad line doesn't hide an entire history of good
    ones; use `goldenboy.analytics.data_quality` for a full quality report."""

    def __init__(self, history_dir: str = ".goldenboy", filename: str = "history.jsonl"):
        self.history_dir = history_dir
        self.history_file = os.path.join(history_dir, filename)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def append(self, event: TaskEvent) -> None:
        self._ensure_dir()
        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except OSError as e:
            raise HistoryError(f"Could not write to history log at '{self.history_file}': {e}") from e

    def load_events(self) -> "LoadResult":
        if not os.path.exists(self.history_file):
            return LoadResult(events=[], total_lines=0, corrupted_lines=0)

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise HistoryError(f"Could not read history log at '{self.history_file}': {e}") from e

        events: List[TaskEvent] = []
        corrupted = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                events.append(TaskEvent.from_dict(data))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                corrupted += 1

        return LoadResult(events=events, total_lines=len(lines), corrupted_lines=corrupted)

    def clear(self) -> None:
        if os.path.exists(self.history_file):
            os.remove(self.history_file)


@dataclass
class LoadResult:
    events: List[TaskEvent]
    total_lines: int
    corrupted_lines: int

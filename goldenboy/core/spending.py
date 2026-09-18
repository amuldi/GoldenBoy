"""Session/day-level spend tracking, on top of `Budget`'s existing
per-check percentage semantics.

`Budget`/`RiskEngine` (see `goldenboy.core.budget`/`goldenboy.core.risk`)
answer "is *this* estimated cost safe against the budget *right now*." They
were never meant to answer a different, cumulative question: "how much has
actually been spent this session, or today, across many separate
requests?" -- nothing in the existing budget/risk layer accumulates state
across calls (each `Budget`/`TaskEstimate` is a fresh snapshot). This
module adds that accumulation, in absolute tokens (not just a percentage),
as an explicit, separate, additive layer -- `Budget`/`RiskEngine`
themselves are unchanged.

Every entry is one JSON line in `.goldenboy/spending.jsonl`, same
append-only convention as `HistoryStore`/`TelemetryStore`
(never stores raw task text; tolerant of corrupted lines).

Honesty note: `estimated_tokens` and `actual_tokens` are always kept
distinct in every field name and every rendered summary -- see
`LedgerSummary.render()`. An estimate is never displayed as if it were a
measured actual.
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.errors import GoldenBoyError

SPENDING_SCHEMA_VERSION = 1


class SpendingError(GoldenBoyError):
    """The spending log could not be read (I/O failure) -- distinct from a
    single malformed line, which `load_events` reports as a count rather
    than raising."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class SpendEntry:
    """One recorded spend -- a task's estimated token cost, and (once
    known) its actual token cost. `actual_tokens=None` means "not yet
    measured," not "zero" -- `LedgerSummary` treats the two very
    differently (see its docstring)."""

    schema_version: int
    timestamp: str
    label: str
    estimated_tokens: int
    actual_tokens: Optional[int] = None
    task_type: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        label: str,
        estimated_tokens: int,
        actual_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "SpendEntry":
        if estimated_tokens < 0:
            raise ValueError(f"estimated_tokens must be >= 0, got {estimated_tokens!r}.")
        if actual_tokens is not None and actual_tokens < 0:
            raise ValueError(f"actual_tokens must be >= 0 or None, got {actual_tokens!r}.")
        return cls(
            schema_version=SPENDING_SCHEMA_VERSION,
            timestamp=_utcnow_iso(),
            label=label,
            estimated_tokens=estimated_tokens,
            actual_tokens=actual_tokens,
            task_type=task_type,
            extra=extra or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpendEntry":
        required = ("schema_version", "timestamp", "label", "estimated_tokens")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"missing field(s): {', '.join(missing)}")
        return cls(
            schema_version=data["schema_version"],
            timestamp=data["timestamp"],
            label=data["label"],
            estimated_tokens=data["estimated_tokens"],
            actual_tokens=data.get("actual_tokens"),
            task_type=data.get("task_type"),
            extra=data.get("extra", {}),
        )


@dataclass
class SpendingLoadResult:
    entries: List[SpendEntry]
    total_lines: int
    corrupted_lines: int


class SpendingStore:
    """Append-only JSONL log of `SpendEntry`, same conventions as
    `HistoryStore`."""

    def __init__(self, history_dir: str = ".goldenboy", filename: str = "spending.jsonl"):
        self.history_dir = history_dir
        self.spending_file = os.path.join(history_dir, filename)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def append(self, entry: SpendEntry) -> None:
        self._ensure_dir()
        try:
            with open(self.spending_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except OSError as e:
            raise SpendingError(f"Could not write to spending log at '{self.spending_file}': {e}") from e

    def load_events(self) -> SpendingLoadResult:
        if not os.path.exists(self.spending_file):
            return SpendingLoadResult(entries=[], total_lines=0, corrupted_lines=0)
        try:
            with open(self.spending_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise SpendingError(f"Could not read spending log at '{self.spending_file}': {e}") from e

        entries: List[SpendEntry] = []
        corrupted = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(SpendEntry.from_dict(json.loads(stripped)))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                corrupted += 1
        return SpendingLoadResult(entries=entries, total_lines=len(lines), corrupted_lines=corrupted)

    def clear(self) -> None:
        if os.path.exists(self.spending_file):
            os.remove(self.spending_file)


@dataclass
class LedgerSummary:
    """A rollup of a set of `SpendEntry` rows against an optional token
    limit. `committed_tokens` (the number budget enforcement should
    actually compare against a limit) uses `actual_tokens` for any entry
    where it's known, and falls back to `estimated_tokens` only for entries
    still awaiting a real measurement -- this is what makes "Remaining" in
    the project brief's worked example come out right (a settled entry's
    estimate stops counting once its actual is known)."""

    window: str  # "session" | "daily" | "all"
    limit_tokens: Optional[int]
    entry_count: int
    estimated_tokens_total: int
    actual_tokens_total: int
    settled_count: int
    committed_tokens: int
    remaining_tokens: Optional[int]
    over_limit: bool

    def render(self) -> str:
        lines = [
            f"Spending ledger ({self.window}) -- {self.entry_count} entrie(s), {self.settled_count} settled"
        ]
        lines.append(f"  Estimated (sum of all entries): {self.estimated_tokens_total:,} tokens")
        lines.append(f"  Actual (sum of settled entries): {self.actual_tokens_total:,} tokens")
        lines.append(f"  Committed (actual where known, else estimated): {self.committed_tokens:,} tokens")
        if self.limit_tokens is not None:
            lines.append(f"  Budget limit: {self.limit_tokens:,} tokens")
            remaining = self.remaining_tokens if self.remaining_tokens is not None else 0
            lines.append(f"  Remaining: {remaining:,} tokens" + (" (OVER LIMIT)" if self.over_limit else ""))
        return "\n".join(lines)


def _entry_date(entry: SpendEntry) -> str:
    try:
        return entry.timestamp.split("T")[0]
    except (AttributeError, IndexError):  # pragma: no cover - defensive
        return ""


def filter_since(entries: List[SpendEntry], since_iso: str) -> List[SpendEntry]:
    """Entries at or after `since_iso` (ISO 8601 string, string-comparable
    since both are UTC and the same format `_utcnow_iso()` produces) --
    used for a "session" window anchored at a caller-recorded start time."""
    return [e for e in entries if e.timestamp >= since_iso]


def filter_today(entries: List[SpendEntry]) -> List[SpendEntry]:
    """Entries whose UTC calendar date matches today. Deliberately a
    calendar-day boundary, not a rolling 24h window -- simpler and
    deterministic to test, and documented as such rather than implying
    rolling-window precision this module doesn't actually provide."""
    today = _utcnow_date()
    return [e for e in entries if _entry_date(e) == today]


def summarize(
    entries: List[SpendEntry], limit_tokens: Optional[int] = None, window: str = "all"
) -> LedgerSummary:
    estimated_total = sum(e.estimated_tokens for e in entries)
    actual_total = sum(e.actual_tokens for e in entries if e.actual_tokens is not None)
    settled = sum(1 for e in entries if e.actual_tokens is not None)
    committed = sum(
        e.actual_tokens if e.actual_tokens is not None else e.estimated_tokens for e in entries
    )
    remaining = (limit_tokens - committed) if limit_tokens is not None else None
    over_limit = remaining is not None and remaining < 0
    return LedgerSummary(
        window=window,
        limit_tokens=limit_tokens,
        entry_count=len(entries),
        estimated_tokens_total=estimated_total,
        actual_tokens_total=actual_total,
        settled_count=settled,
        committed_tokens=committed,
        remaining_tokens=remaining,
        over_limit=over_limit,
    )


class SessionMarker:
    """Tracks the timestamp a "session" (a run of related `goldenboy`
    invocations -- the CLI itself is stateless per process) is considered
    to have started, persisted next to the spending log so `summarize`'s
    "session" window means something across multiple invocations.
    `.goldenboy/session_start` holds nothing but that one ISO timestamp."""

    def __init__(self, state_dir: str = ".goldenboy", filename: str = "session_start"):
        self.state_dir = state_dir
        self.marker_file = os.path.join(state_dir, filename)

    def get_or_create(self) -> str:
        if os.path.exists(self.marker_file):
            try:
                with open(self.marker_file, "r", encoding="utf-8") as f:
                    value = f.read().strip()
                if value:
                    return value
            except OSError:
                pass
        return self.reset()

    def reset(self) -> str:
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        now = _utcnow_iso()
        with open(self.marker_file, "w", encoding="utf-8") as f:
            f.write(now)
        return now

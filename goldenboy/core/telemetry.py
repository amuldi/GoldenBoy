"""External-agent execution telemetry: what actually happened after Golden
Boy made a decision, reported back by whatever agent did the real work.

Golden Boy does not execute coding tasks itself (see ROADMAP.md's explicit
non-goals) -- it estimates, then hands off. Before this module, there was
no structured way to close that loop: an estimate was made and nothing
about what actually happened afterward was ever recorded in a comparable
shape. This is the missing half of "estimate -> execute -> observe ->
compare" (see the project brief's feedback-loop diagram); calibration
(`goldenboy.core.calibration`) is built entirely on top of this data and
reports N/A/INSUFFICIENT DATA until real records exist here.

Design choices:
    - Every field an external integration might not reliably have is
      Optional; only `final_outcome` and `recorded_at` are required -- a
      report that can only say "it finished" is still useful, and refusing
      to accept anything less would just mean fewer real reports exist to
      learn from (see the project brief: "Do not require fields that an
      external integration cannot reliably provide").
    - Self-contained: a record carries both the *estimated* figures the
      caller received from `goldenboy analyze` (echoed back, not
      re-derived -- a stale echo is then visible as a mismatch, not
      silently "corrected") and the *actual* figures it measured, so
      calibration never needs to join against a separate decision log by
      some fragile shared id. `task_id`/`execution_id` are still accepted,
      purely for the caller's own correlation/debugging.
    - Same append-only JSONL convention as `HistoryStore` (see that
      module's docstring), but its own file (`.goldenboy/telemetry.jsonl`)
      rather than overloading `history.jsonl`'s narrower, decision-time
      schema with a second, differently-shaped record.
    - Never stores raw prompt/diff text -- only counts. Same privacy
      posture as `HistoryStore` (see SECURITY.md).
"""
import json
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.config import get_default_config
from goldenboy.core.errors import GoldenBoyError

TELEMETRY_SCHEMA_VERSION = 1

# "partial": genuinely started and produced some result, but neither a
# clean completion nor an outright failure (e.g. deferred mid-way under
# budget pressure). Distinct from HistoryStore's TaskEvent.outcome
# vocabulary ("completed"/"deferred"/"failed") on purpose -- that field
# describes Golden Boy's own decision-time outcome; this one describes
# what an external agent's *execution* actually concluded with.
VALID_OUTCOMES = {"completed", "failed", "partial"}

# Section 18 ("verification must be a first-class concept") vocabulary:
# whether the claimed outcome was actually backed by collected evidence
# (e.g. a real test-run exit code), not just a claim. None means "not
# reported" -- distinct from any of these four.
VALID_VERIFICATION_STATUSES = {"VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED", "FAILED"}


class TelemetryError(GoldenBoyError):
    """The telemetry log could not be read (I/O failure) -- distinct from a
    single malformed line, which `load_events` reports as a count rather
    than raising."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExecutionTelemetry:
    """One reported execution outcome. See module docstring for the design
    rationale -- construct via `create()`, which validates `final_outcome`/
    `verification_status` and derives `actual_cost_percentage`."""

    schema_version: int
    recorded_at: str
    final_outcome: str  # "completed" | "failed" | "partial"
    verification_status: Optional[str] = None
    failure_reason: Optional[str] = None

    task_id: Optional[str] = None
    execution_id: Optional[str] = None

    # Echoed from the `goldenboy analyze` output this execution acted on
    # (`task.task_type`, `task.estimated_cost_percentage`,
    # `task.estimated_cost_confidence`) -- not re-derived, so calibration
    # can break results down by category (see `goldenboy.core.calibration`)
    # without re-running the classifier against a task text this module
    # never sees and does not store.
    task_type: Optional[str] = None
    estimated_cost_percentage: Optional[float] = None
    estimated_cost_confidence: Optional[float] = None

    actual_input_tokens: Optional[int] = None
    actual_output_tokens: Optional[int] = None
    actual_total_tokens: Optional[int] = None
    actual_cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None

    tool_calls: Optional[int] = None
    files_touched: Optional[int] = None
    lines_added: Optional[int] = None
    lines_removed: Optional[int] = None

    tests_run: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    retry_count: Optional[int] = None

    # Derived at create() time from actual_total_tokens / max_budget_tokens
    # (caller-supplied, else Golden Boy's own default config) -- the same
    # percentage scale `estimated_cost_percentage` is already on, so the
    # two are directly comparable without the caller doing that math, and
    # without calibration needing to re-derive it later from a config that
    # may since have changed.
    actual_cost_percentage: Optional[float] = None
    max_budget_tokens: Optional[int] = None

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        final_outcome: str,
        verification_status: Optional[str] = None,
        failure_reason: Optional[str] = None,
        task_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        task_type: Optional[str] = None,
        estimated_cost_percentage: Optional[float] = None,
        estimated_cost_confidence: Optional[float] = None,
        actual_input_tokens: Optional[int] = None,
        actual_output_tokens: Optional[int] = None,
        actual_total_tokens: Optional[int] = None,
        actual_cost_usd: Optional[float] = None,
        duration_seconds: Optional[float] = None,
        tool_calls: Optional[int] = None,
        files_touched: Optional[int] = None,
        lines_added: Optional[int] = None,
        lines_removed: Optional[int] = None,
        tests_run: Optional[int] = None,
        tests_passed: Optional[int] = None,
        tests_failed: Optional[int] = None,
        retry_count: Optional[int] = None,
        max_budget_tokens: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionTelemetry":
        if final_outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"final_outcome must be one of {sorted(VALID_OUTCOMES)}, got {final_outcome!r}."
            )
        if verification_status is not None and verification_status not in VALID_VERIFICATION_STATUSES:
            raise ValueError(
                f"verification_status must be one of {sorted(VALID_VERIFICATION_STATUSES)} or None, "
                f"got {verification_status!r}."
            )

        effective_budget = max_budget_tokens
        if effective_budget is None:
            effective_budget = get_default_config().max_budget_tokens

        actual_cost_percentage = None
        if actual_total_tokens is not None and effective_budget:
            actual_cost_percentage = round((actual_total_tokens / effective_budget) * 100.0, 4)

        return cls(
            schema_version=TELEMETRY_SCHEMA_VERSION,
            recorded_at=_utcnow_iso(),
            final_outcome=final_outcome,
            verification_status=verification_status,
            failure_reason=failure_reason,
            task_id=task_id,
            execution_id=execution_id,
            task_type=task_type,
            estimated_cost_percentage=estimated_cost_percentage,
            estimated_cost_confidence=estimated_cost_confidence,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            actual_total_tokens=actual_total_tokens,
            actual_cost_usd=actual_cost_usd,
            duration_seconds=duration_seconds,
            tool_calls=tool_calls,
            files_touched=files_touched,
            lines_added=lines_added,
            lines_removed=lines_removed,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            retry_count=retry_count,
            actual_cost_percentage=actual_cost_percentage,
            max_budget_tokens=effective_budget,
            extra=extra or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionTelemetry":
        required = ("schema_version", "recorded_at", "final_outcome")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"missing field(s): {', '.join(missing)}")
        known_fields = {f.name for f in fields(cls)}
        unknown_dropped = {k: v for k, v in data.items() if k in known_fields}
        return cls(**unknown_dropped)


@dataclass
class TelemetryLoadResult:
    events: List[ExecutionTelemetry]
    total_lines: int
    corrupted_lines: int


class TelemetryStore:
    """Append-only JSONL log of `ExecutionTelemetry`, same conventions as
    `HistoryStore` (see that class's docstring): `append()` never raises on
    a write it can't cleanly complete except a genuine I/O failure
    (`TelemetryError`); `load_events()` tolerates individual corrupted
    lines rather than losing an entire log to one bad line."""

    def __init__(self, history_dir: str = ".goldenboy", filename: str = "telemetry.jsonl"):
        self.history_dir = history_dir
        self.telemetry_file = os.path.join(history_dir, filename)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def append(self, event: ExecutionTelemetry) -> None:
        self._ensure_dir()
        try:
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except OSError as e:
            raise TelemetryError(
                f"Could not write to telemetry log at '{self.telemetry_file}': {e}"
            ) from e

    def load_events(self) -> TelemetryLoadResult:
        if not os.path.exists(self.telemetry_file):
            return TelemetryLoadResult(events=[], total_lines=0, corrupted_lines=0)

        try:
            with open(self.telemetry_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise TelemetryError(
                f"Could not read telemetry log at '{self.telemetry_file}': {e}"
            ) from e

        events: List[ExecutionTelemetry] = []
        corrupted = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                events.append(ExecutionTelemetry.from_dict(data))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                corrupted += 1

        return TelemetryLoadResult(events=events, total_lines=len(lines), corrupted_lines=corrupted)

    def clear(self) -> None:
        if os.path.exists(self.telemetry_file):
            os.remove(self.telemetry_file)

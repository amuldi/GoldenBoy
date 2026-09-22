"""Audit Log: a local, append-only record of Golden Boy's own governance
decisions -- what was requested, what the Policy Engine decided, what it
cost, and how it turned out.

Same on-disk convention as `HistoryStore`/`TelemetryStore` (see those
modules): one JSON object per line in `.goldenboy/audit.jsonl`, gitignored,
never sent anywhere, tolerant of individual corrupted lines rather than
losing an entire log to one bad one. Distinct from `HistoryStore` in scope:
`HistoryStore` records `budget_aware_execution`'s own decisions for
analytics/replay; `AuditStore` records arbitrary governance-relevant events
(policy checks, snapshot verifications, and anything else a caller wants a
human-reviewable trail of) with a wider, more free-form field set.

Privacy: `error`/`extra` free-text fields are passed through
`goldenboy.core.redaction.redact_secrets` before being written -- see that
module's docstring. Never store an API key, token, or password here.
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.redaction import redact_secrets

AUDIT_SCHEMA_VERSION = 1

# What `AuditEntry.result` is drawn from -- not a strict enum on the
# dataclass itself (JSONL readers from other tools shouldn't be broken by a
# value this module doesn't yet know about), but validated at construction
# time via `create()` so a typo is caught immediately rather than silently
# persisted.
VALID_RESULTS = {"success", "failure", "blocked", "pending_approval", "skipped"}


class EventType:
    """A suggested, not enforced, vocabulary of `AuditEntry.action` values
    spanning one task's execution lifecycle end-to-end (see the project
    brief's "Execution Trace / Audit" section) -- estimate -> policy check
    -> execution -> verification -> retry/escalation -> completion.

    `action` on `AuditEntry` stays a free-form string, same as before
    (`PolicyEngine` already records `"policy_check"`, matched here by
    `POLICY_CHECKED`, unchanged for backward compatibility). These
    constants exist so callers that want `goldenboy trace` to render a
    coherent, ordered story use consistent names instead of each picking
    their own -- not because a `goldenboy audit`/`AuditStore` write is
    rejected for using a different one.
    """

    TASK_STARTED = "task_started"
    ESTIMATE_CREATED = "estimate_created"
    POLICY_CHECKED = "policy_check"
    ACTION_ALLOWED = "action_allowed"
    ACTION_EXECUTED = "action_executed"
    VERIFICATION_FAILED = "verification_failed"
    FAILURE_CLASSIFIED = "failure_classified"
    RETRY_STARTED = "retry_started"
    RISK_ESCALATED = "risk_escalated"
    APPROVAL_REQUIRED = "approval_required"
    ROLLBACK_STARTED = "rollback_started"
    TASK_COMPLETED = "task_completed"


class AuditError(GoldenBoyError):
    """The audit log could not be read (I/O failure) -- distinct from a
    single malformed line, which `load_events` reports as a count rather
    than raising."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEntry:
    """One recorded governance event. Every field but `timestamp`/`action`/
    `result` is optional -- an audit entry that can only say "this action
    happened and here's how it turned out" is still useful, and requiring
    fields a caller may not have (e.g. `actual_cost` before execution
    finishes) would just mean fewer real events get recorded."""

    schema_version: int
    timestamp: str
    action: str
    result: str  # one of VALID_RESULTS
    task_id: Optional[str] = None
    tool: Optional[str] = None
    decision: Optional[str] = None       # e.g. a PolicyVerdict value
    policy_result: Optional[str] = None  # e.g. a policy reason_code
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        action: str,
        result: str,
        task_id: Optional[str] = None,
        tool: Optional[str] = None,
        decision: Optional[str] = None,
        policy_result: Optional[str] = None,
        estimated_cost: Optional[float] = None,
        actual_cost: Optional[float] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "AuditEntry":
        if result not in VALID_RESULTS:
            raise ValueError(f"result must be one of {sorted(VALID_RESULTS)}, got {result!r}.")
        if not action or not action.strip():
            raise ValueError("action must be a non-empty string.")

        safe_extra = {
            k: (redact_secrets(v) if isinstance(v, str) else v) for k, v in (extra or {}).items()
        }

        return cls(
            schema_version=AUDIT_SCHEMA_VERSION,
            timestamp=_utcnow_iso(),
            action=action,
            result=result,
            task_id=task_id,
            tool=tool,
            decision=decision,
            policy_result=policy_result,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            error=redact_secrets(error) if error else error,
            duration_seconds=duration_seconds,
            extra=safe_extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        required = ("schema_version", "timestamp", "action", "result")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"missing field(s): {', '.join(missing)}")
        return cls(
            schema_version=data["schema_version"],
            timestamp=data["timestamp"],
            action=data["action"],
            result=data["result"],
            task_id=data.get("task_id"),
            tool=data.get("tool"),
            decision=data.get("decision"),
            policy_result=data.get("policy_result"),
            estimated_cost=data.get("estimated_cost"),
            actual_cost=data.get("actual_cost"),
            error=data.get("error"),
            duration_seconds=data.get("duration_seconds"),
            extra=data.get("extra", {}),
        )

    def render(self) -> str:
        """The human-readable block format from the project brief -- only
        fields that are actually set are shown."""
        if "T" in self.timestamp:
            clock = self.timestamp.split("T")[-1].split("+")[0].split(".")[0]
        else:
            clock = self.timestamp
        lines = [f"[{clock}]"]
        if self.task_id:
            lines.append(f"TASK: {self.task_id}")
        lines.append(f"ACTION: {self.action}")
        if self.tool:
            lines.append(f"TOOL: {self.tool}")
        if self.decision:
            policy_line = f"POLICY: {self.decision}"
            if self.policy_result:
                policy_line += f" ({self.policy_result})"
            lines.append(policy_line)
        if self.estimated_cost is not None:
            lines.append(f"ESTIMATED: {self.estimated_cost:,.0f} tokens")
        if self.actual_cost is not None:
            lines.append(f"ACTUAL: {self.actual_cost:,.0f} tokens")
        lines.append(f"RESULT: {self.result}")
        if self.error:
            lines.append(f"ERROR: {self.error}")
        return "\n".join(lines)


@dataclass
class AuditLoadResult:
    events: List[AuditEntry]
    total_lines: int
    corrupted_lines: int


class AuditStore:
    """Append-only JSONL log, same conventions as `HistoryStore`."""

    def __init__(self, history_dir: str = ".goldenboy", filename: str = "audit.jsonl"):
        self.history_dir = history_dir
        self.audit_file = os.path.join(history_dir, filename)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)

    def record(self, entry: AuditEntry) -> None:
        self._ensure_dir()
        try:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except OSError as e:
            raise AuditError(f"Could not write to audit log at '{self.audit_file}': {e}") from e

    def load_events(self) -> AuditLoadResult:
        if not os.path.exists(self.audit_file):
            return AuditLoadResult(events=[], total_lines=0, corrupted_lines=0)

        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise AuditError(f"Could not read audit log at '{self.audit_file}': {e}") from e

        events: List[AuditEntry] = []
        corrupted = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                events.append(AuditEntry.from_dict(data))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                corrupted += 1

        return AuditLoadResult(events=events, total_lines=len(lines), corrupted_lines=corrupted)

    def trace(self, task_id: str) -> List[AuditEntry]:
        """Every recorded entry for one `task_id`, in the order they were
        written (the log is append-only, so file order is chronological
        order) -- one task's full governance/execution story, distinct
        from `load_events()`'s unfiltered, recency-limited view used by
        `goldenboy audit`. Entries recorded without a `task_id` are never
        included (there is nothing to match them to)."""
        return [e for e in self.load_events().events if e.task_id == task_id]

    def clear(self) -> None:
        if os.path.exists(self.audit_file):
            os.remove(self.audit_file)

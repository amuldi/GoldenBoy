"""The Golden Boy Protocol: a versioned, language-neutral data contract.

Everything Golden Boy's CLI (`--json`) and Python API report as a decision is
a `GoldenBoyDecision` — one stable, serializable shape that a calling agent
(in any language) can depend on without importing this package. This module
is the *only* place that shape is defined; `cli.py`, `decision_engine.py`,
and the TypeScript SDK (`sdk/typescript/`) all target the same schema.

Design constraints (see ROADMAP.md / ARCHITECTURE for the reasoning):
    - versioned: every payload carries `schema_version`; a breaking change
      bumps the major component and `from_dict` refuses to silently
      misread an incompatible payload (mirrors `CheckpointManager`'s
      version guard).
    - provider- and language-independent: plain dataclasses of str/float/
      bool/list/dict, JSON-serializable with no custom types leaking out.
    - strict validation: `from_dict` raises `ProtocolError` with a specific,
      actionable message on a missing/malformed field, never a raw
      `KeyError`/`TypeError`.
    - no network dependency: this module has zero imports beyond the
      standard library.
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from goldenboy.core.errors import GoldenBoyError

# Bump the major segment for a breaking change (field removed/repurposed);
# bump minor/patch for additive, backward-compatible changes. `from_dict`
# only rejects a payload whose *major* version it doesn't understand --
# the same tolerance CheckpointManager applies to its own schema version.
#
# 1.1.0: additive `TaskProfile.complexity_signals` field, plus a behavior
# change to how the existing `TaskProfile.complexity` value is computed
# (see that field's docstring) -- shape is unchanged and old readers using
# `.get("complexity_signals", [])` degrade gracefully, so this is a minor
# bump, not major.
PROTOCOL_VERSION = "1.1.0"


class ProtocolError(GoldenBoyError):
    """A Golden Boy Protocol payload is malformed, missing required fields,
    or was produced by an incompatible major schema version."""


def _major(version: str) -> str:
    return version.split(".", 1)[0]


def _require(data: Dict[str, Any], key: str, context: str) -> Any:
    if key not in data:
        raise ProtocolError(f"{context} is missing required field '{key}'.")
    return data[key]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskProfile:
    """What Golden Boy believes about the task itself."""

    task_type: str
    task_type_confidence: float
    # 0.0-1.0, heuristic weighted-signal strength from
    # `goldenboy.core.complexity.estimate_task_complexity` -- NOT a
    # calibrated probability. `complexity_signals` below names which fixed
    # signals fired (see that module). Prior schema versions derived this
    # value from the cost estimate instead of the task text directly; the
    # field name and type are unchanged, only how it's computed.
    complexity: float
    complexity_label: str  # LOW / MEDIUM / HIGH / VERY_HIGH
    estimated_cost_percentage: float
    estimated_cost_confidence: float
    signals: Dict[str, int] = field(default_factory=dict)
    complexity_signals: List[str] = field(default_factory=list)
    # Other task types that also scored meaningfully, alongside the
    # primary `task_type` above -- see
    # `goldenboy.core.task_classifier.TaskClassification.secondary_task_types`.
    # Added in PROTOCOL_VERSION 1.1.0; absent on payloads from older writers.
    secondary_task_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskProfile":
        ctx = "TaskProfile"
        return cls(
            task_type=_require(data, "task_type", ctx),
            task_type_confidence=_require(data, "task_type_confidence", ctx),
            complexity=_require(data, "complexity", ctx),
            complexity_label=_require(data, "complexity_label", ctx),
            estimated_cost_percentage=_require(data, "estimated_cost_percentage", ctx),
            estimated_cost_confidence=_require(data, "estimated_cost_confidence", ctx),
            signals=data.get("signals", {}),
            complexity_signals=data.get("complexity_signals", []),
            secondary_task_types=data.get("secondary_task_types", []),
        )


@dataclass
class UsageSnapshot:
    """What Golden Boy believes about remaining budget."""

    remaining_percentage: float
    usable_percentage: float
    source: str
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageSnapshot":
        ctx = "UsageSnapshot"
        return cls(
            remaining_percentage=_require(data, "remaining_percentage", ctx),
            usable_percentage=_require(data, "usable_percentage", ctx),
            source=_require(data, "source", ctx),
            confidence=_require(data, "confidence", ctx),
        )


@dataclass
class RiskAssessment:
    """The risk mode and *why* — a reason code, not just a label."""

    mode: str  # ExecutionMode.value
    reason_code: str
    ratio: Optional[float] = None  # estimated_cost / usable_percentage, when defined

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        ctx = "RiskAssessment"
        return cls(
            mode=_require(data, "mode", ctx),
            reason_code=_require(data, "reason_code", ctx),
            ratio=data.get("ratio"),
        )


@dataclass
class GoldenBoyDecision:
    """The single, stable output shape Golden Boy produces for a task.

    This is the payload `goldenboy analyze --json` prints, and what
    `DecisionEngine.decide()` returns. Every field is derived from an
    actual measurement made this call (Estimator, RiskEngine, the task
    classifier, and the caller-supplied progress) -- nothing here is a
    template filled with invented numbers.
    """

    schema_version: str
    generated_at: str
    task: TaskProfile
    usage: UsageSnapshot
    risk: RiskAssessment
    action: str
    confidence: float
    reason: str
    recommendation: List[str] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        task: TaskProfile,
        usage: UsageSnapshot,
        risk: RiskAssessment,
        action: str,
        confidence: float,
        reason: str,
        recommendation: Optional[List[str]] = None,
    ) -> "GoldenBoyDecision":
        return cls(
            schema_version=PROTOCOL_VERSION,
            generated_at=_utcnow_iso(),
            task=task,
            usage=usage,
            risk=risk,
            action=action,
            confidence=confidence,
            reason=reason,
            recommendation=recommendation or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "task": self.task.to_dict(),
            "usage": self.usage.to_dict(),
            "risk": self.risk.to_dict(),
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "recommendation": list(self.recommendation),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenBoyDecision":
        ctx = "GoldenBoyDecision"
        if not isinstance(data, dict):
            raise ProtocolError(f"{ctx} payload must be a JSON object, got {type(data).__name__}.")

        version = _require(data, "schema_version", ctx)
        if _major(version) != _major(PROTOCOL_VERSION):
            raise ProtocolError(
                f"{ctx} payload has schema_version={version!r}, which is not compatible with "
                f"this Golden Boy's protocol major version ({PROTOCOL_VERSION}). "
                "Upgrade the reader/writer so both sides agree on a major version."
            )

        try:
            return cls(
                schema_version=version,
                generated_at=_require(data, "generated_at", ctx),
                task=TaskProfile.from_dict(_require(data, "task", ctx)),
                usage=UsageSnapshot.from_dict(_require(data, "usage", ctx)),
                risk=RiskAssessment.from_dict(_require(data, "risk", ctx)),
                action=_require(data, "action", ctx),
                confidence=_require(data, "confidence", ctx),
                reason=_require(data, "reason", ctx),
                recommendation=data.get("recommendation", []),
            )
        except ProtocolError:
            raise
        except (KeyError, TypeError, ValueError) as e:
            raise ProtocolError(f"{ctx} payload is malformed: {e}") from e

    @classmethod
    def from_json(cls, raw: str) -> "GoldenBoyDecision":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProtocolError(f"GoldenBoyDecision payload is not valid JSON: {e}") from e
        return cls.from_dict(data)

"""Risk Budget: cumulative, point-based risk accounting across a session --
distinct from, and complementary to, the two risk-shaped things Golden Boy
already has:

    - `goldenboy.core.risk.RiskEngine` answers "will this *task* exceed the
      token budget?" from a budget-ratio, per-assessment, stateless
      calculation (SAFE/CAUTION/LIMITED/CRITICAL).
    - `goldenboy.core.governance.PolicyEngine` answers "is this *one action*
      itself allowed right now?" from rule/pattern matching, also stateless
      per call.
    - This module answers a third, different question: "how much risk has
      this session already spent, across every action so far, and does
      *that running total* now require approval or a stop?"

State is cumulative and persists across calls (`.goldenboy/risk_budget_state.json`,
distinct from the `.goldenboy/risk_budget.json` *config* file below -- same
state/config split as `LoopDetector`'s `loop_state.json` vs. this module's
own config) and is monotonic: `record()`
only ever deducts from the remaining budget; nothing here restores it on a
success. That monotonicity is deliberate -- it is what makes the model
"adaptive" in the sense the project brief means: permissions tighten
(ALLOW -> REQUIRE_APPROVAL -> DENY) as risk accumulates within a session,
and never loosen on their own. A caller who wants a fresh session calls
`reset()` explicitly.

`repeat_count` lets a caller feed in a signal it already has (e.g.
`LoopDetector.record().count` or a `FailureRecord.attempt_count` for the
same signature) so a *repeated* failure costs more than the first
occurrence, without this module needing to know anything about loops or
failures itself -- same "caller supplies the already-known facts" shape as
`ActionRequest` in `goldenboy.core.governance`.

Operation weights below are the project brief's example values, not a
measured or validated risk model -- see `RiskBudgetConfig` docstring. They
are fully overridable via `.goldenboy/risk_budget.json` (or an explicit
`RiskBudgetConfig(...)`), same override cascade as `PolicyConfig`/
`GoldenBoyConfig`. Golden Boy does not claim these numbers are "correct"
risk weights for any given project -- only that the accounting is
transparent, deterministic, and inspectable.
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.governance import PolicyVerdict

RISK_BUDGET_SCHEMA_VERSION = 1

_ENV_PREFIX = "GOLDENBOY_RISK_BUDGET_"

# Example weights from the project brief -- deliberately not fit to any
# data. A caller with real incident history for their own project should
# override these via `.goldenboy/risk_budget.json`.
_DEFAULT_OPERATION_WEIGHTS: Dict[str, float] = {
    "read_file": 1.0,
    "modify_source": 3.0,
    "modify_many_files": 5.0,
    "dependency_change": 10.0,
    "shell_command": 8.0,
    "ci_configuration": 20.0,
    "sensitive_path": 20.0,
    "dangerous_operation": 40.0,
}
_DEFAULT_UNKNOWN_OPERATION_WEIGHT = 2.0


class RiskBudgetError(GoldenBoyError):
    """The risk-budget config or state file exists but is invalid."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RiskBudgetConfig:
    """Cumulative risk-budget thresholds and per-operation weights.

    Attributes:
        initial_budget: The risk budget a fresh session starts with (and
            what `reset()` returns to). Not a percentage of anything else
            in Golden Boy -- its own independent scale, in points.
        operation_weights: Maps a caller-supplied operation-kind string
            (e.g. "shell_command") to how many points one occurrence costs.
            An operation kind not in this map falls back to
            `unknown_operation_weight`, never to zero -- an unrecognized
            operation is not free.
        unknown_operation_weight: Weight applied to any `record()` call
            whose `operation` isn't a key in `operation_weights`.
        repeat_failure_penalty: Extra points deducted per repeat *beyond
            the first*, when a caller passes `repeat_count > 1` to
            `record()` (e.g. from `LoopDetector`/`FailureMemoryStore` for
            the same signature). Models the idea that retrying the same
            failing action is itself a risk signal, distinct from the
            operation's own base weight.
        approval_threshold: Once `remaining` falls to or below this value,
            `record()` returns `REQUIRE_APPROVAL`. Must be strictly between
            `deny_threshold` and `initial_budget`.
        deny_threshold: Once `remaining` falls to or below this value,
            `record()` returns `DENY`. Must be `>= 0` and `<
            approval_threshold`.

    Raises:
        RiskBudgetError: if constructed with an invalid threshold ordering
            or a negative weight.
    """

    initial_budget: float = 100.0
    operation_weights: Dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_OPERATION_WEIGHTS)
    )
    unknown_operation_weight: float = _DEFAULT_UNKNOWN_OPERATION_WEIGHT
    repeat_failure_penalty: float = 5.0
    approval_threshold: float = 40.0
    deny_threshold: float = 10.0

    def __post_init__(self) -> None:
        if self.initial_budget <= 0:
            raise RiskBudgetError("initial_budget must be > 0.")
        if self.deny_threshold < 0:
            raise RiskBudgetError("deny_threshold must be >= 0.")
        if not (self.deny_threshold < self.approval_threshold <= self.initial_budget):
            raise RiskBudgetError(
                "thresholds must satisfy deny_threshold < approval_threshold <= initial_budget "
                f"(got deny_threshold={self.deny_threshold}, approval_threshold={self.approval_threshold}, "
                f"initial_budget={self.initial_budget})."
            )
        if self.unknown_operation_weight < 0 or self.repeat_failure_penalty < 0:
            raise RiskBudgetError("unknown_operation_weight and repeat_failure_penalty must be >= 0.")
        for op, weight in self.operation_weights.items():
            if weight < 0:
                raise RiskBudgetError(f"operation_weights[{op!r}] must be >= 0, got {weight!r}.")

    @classmethod
    def load(cls, config_path: str = ".goldenboy/risk_budget.json") -> "RiskBudgetConfig":
        """Defaults, then a JSON file if present, then env vars for the
        scalar fields (not `operation_weights`, same convention as
        `PolicyConfig.denied_command_patterns` -- a dict override belongs
        in a file, not a single env var). A missing file is not an error;
        a present-but-broken one raises `RiskBudgetError`."""
        values: Dict[str, object] = {}
        valid_keys = {f for f in cls.__dataclass_fields__}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_values = json.load(f)
            except json.JSONDecodeError as e:
                raise RiskBudgetError(
                    f"Could not parse risk-budget config at '{config_path}': {e}. "
                    "Fix the JSON syntax, or remove the file to use defaults."
                ) from e
            except OSError as e:
                raise RiskBudgetError(f"Could not read risk-budget config at '{config_path}': {e}") from e

            if not isinstance(file_values, dict):
                raise RiskBudgetError(
                    f"Risk-budget config at '{config_path}' must contain a JSON object, "
                    f"got {type(file_values).__name__}."
                )
            unknown = sorted(set(file_values) - valid_keys)
            if unknown:
                raise RiskBudgetError(
                    f"Risk-budget config at '{config_path}' has unknown key(s): {', '.join(unknown)} "
                    f"(valid keys: {', '.join(sorted(valid_keys))})."
                )
            values.update(file_values)

        for numeric_field in (
            "initial_budget", "unknown_operation_weight", "repeat_failure_penalty",
            "approval_threshold", "deny_threshold",
        ):
            raw = os.getenv(_ENV_PREFIX + numeric_field.upper())
            if raw is None:
                continue
            try:
                values[numeric_field] = float(raw)
            except ValueError as e:
                raise RiskBudgetError(
                    f"Environment variable {_ENV_PREFIX + numeric_field.upper()}={raw!r} "
                    "is not a valid number."
                ) from e

        return cls(**values)  # type: ignore[arg-type]


@dataclass
class RiskBudgetState:
    schema_version: int
    remaining: float
    total_deducted: float
    operations_recorded: int
    last_operation: Optional[str]
    last_updated: Optional[str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "RiskBudgetState":
        return cls(
            schema_version=data["schema_version"],  # type: ignore[arg-type]
            remaining=data["remaining"],  # type: ignore[arg-type]
            total_deducted=data["total_deducted"],  # type: ignore[arg-type]
            operations_recorded=data["operations_recorded"],  # type: ignore[arg-type]
            last_operation=data.get("last_operation"),  # type: ignore[arg-type]
            last_updated=data.get("last_updated"),  # type: ignore[arg-type]
        )


@dataclass
class RiskBudgetResult:
    operation: str
    weight_applied: float
    repeat_count: int
    remaining: float
    verdict: PolicyVerdict
    reason: str

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


class RiskBudgetEngine:
    """Tracks one session's cumulative risk spend and returns a verdict on
    each recorded operation. Verdict is always one of `PolicyVerdict.ALLOW`
    / `REQUIRE_APPROVAL` / `DENY` -- the same three-value vocabulary
    `PolicyEngine` uses, reused deliberately rather than duplicated, so a
    caller composing both engines only has one verdict type to handle.
    """

    def __init__(
        self,
        config: Optional[RiskBudgetConfig] = None,
        state_dir: str = ".goldenboy",
        filename: str = "risk_budget_state.json",
    ):
        self.config = config or RiskBudgetConfig.load()
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, filename)

    def _load(self) -> RiskBudgetState:
        if not os.path.exists(self.state_file):
            return RiskBudgetState(
                schema_version=RISK_BUDGET_SCHEMA_VERSION,
                remaining=self.config.initial_budget,
                total_deducted=0.0,
                operations_recorded=0,
                last_operation=None,
                last_updated=None,
            )
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise RiskBudgetError(
                f"Risk-budget state file at '{self.state_file}' is corrupted ({e}). "
                "Remove it to reset, or call reset()."
            ) from e
        except OSError as e:
            raise RiskBudgetError(f"Could not read risk-budget state at '{self.state_file}': {e}") from e
        try:
            return RiskBudgetState.from_dict(data)
        except (KeyError, TypeError) as e:
            raise RiskBudgetError(
                f"Risk-budget state file at '{self.state_file}' is malformed ({e})."
            ) from e

    def _save(self, state: RiskBudgetState) -> None:
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

    def record(self, operation: str, repeat_count: int = 1) -> RiskBudgetResult:
        """Deduct `operation`'s configured weight (plus a repeat-failure
        penalty if `repeat_count > 1`) from the cumulative session budget
        and return the resulting verdict. `remaining` never goes below 0.
        """
        if repeat_count < 1:
            raise ValueError(f"repeat_count must be >= 1, got {repeat_count!r}.")

        weight = self.config.operation_weights.get(operation, self.config.unknown_operation_weight)
        if repeat_count > 1:
            weight += self.config.repeat_failure_penalty * (repeat_count - 1)

        state = self._load()
        state.remaining = max(0.0, state.remaining - weight)
        state.total_deducted += weight
        state.operations_recorded += 1
        state.last_operation = operation
        state.last_updated = _utcnow_iso()
        self._save(state)

        if state.remaining <= self.config.deny_threshold:
            verdict = PolicyVerdict.DENY
            reason = (
                f"Cumulative risk budget exhausted ({state.remaining:.1f} remaining, "
                f"at or below deny threshold {self.config.deny_threshold:.1f})."
            )
        elif state.remaining <= self.config.approval_threshold:
            verdict = PolicyVerdict.REQUIRE_APPROVAL
            reason = (
                f"Cumulative risk budget low ({state.remaining:.1f} remaining, "
                f"at or below approval threshold {self.config.approval_threshold:.1f})."
            )
        else:
            verdict = PolicyVerdict.ALLOW
            reason = f"Cumulative risk budget healthy ({state.remaining:.1f} remaining)."

        return RiskBudgetResult(
            operation=operation, weight_applied=weight, repeat_count=repeat_count,
            remaining=state.remaining, verdict=verdict, reason=reason,
        )

    def status(self) -> RiskBudgetState:
        return self._load()

    def reset(self) -> None:
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

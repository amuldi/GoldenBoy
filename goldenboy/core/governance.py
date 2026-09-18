"""Policy Engine: code-level enforcement of what an agent request is
allowed to do -- distinct from `goldenboy.core.policies` (baseline
proceed/stop policies compared against `RiskEngine` in `goldenboy.replay`).
This module governs actions (tool calls, commands, file writes), not the
proceed/stop backtest question those baselines answer.

Every check here is a deterministic code path over caller-supplied,
already-known facts (tool name, a shell command string, file paths, an
estimated cost, and session/day spend so far) -- never a prompt handed to
an LLM to "decide" on. A verdict is one of three values
(`PolicyVerdict.ALLOW`/`DENY`/`REQUIRE_APPROVAL`); nothing here merely
warns. The caller (an agent runtime, a CLI wrapper, a `goldenboy` command)
is expected to actually refuse to run a DENYed or un-approved action --
Golden Boy cannot force that on its own, since it does not execute
arbitrary work itself (see `goldenboy.adapters.base.ProviderAdapter`'s
docstring / ROADMAP.md's non-goals), but the verdict is unambiguous and
machine-actionable, not advisory prose.

`PolicyEngine.evaluate()` runs four checks in a fixed order, matching the
project brief's pipeline, and returns on the first one that doesn't pass:

    Permission -> Budget -> Risk -> Scope -> ALLOW

Permission: is this tool explicitly denied, or does it require approval
    outright, regardless of anything else about the request?
Budget: would this request exceed a hard per-tool call limit, or a
    session/day spend cap?
Risk: does the request's command text match a known-dangerous or
    known-needs-approval pattern?
Scope: does the request touch a file path outside the allowed scope
    (secrets, VCS internals, etc.)?

All thresholds and patterns live in `PolicyConfig`, loaded the same
defaults -> JSON file -> env-var-override cascade `GoldenBoyConfig` uses
(see `goldenboy.core.config`), from `.goldenboy/policy.json` by default --
never hardcoded inline where a reviewer would have to go hunting for them
(see CONTRIBUTING.md, "No hardcoded policy numbers").
"""
import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from goldenboy.core.errors import PolicyError

_ENV_PREFIX = "GOLDENBOY_POLICY_"

# Fixed, documented defaults -- not fit to any data, deliberately
# conservative. All are overridable via `.goldenboy/policy.json` (see
# `PolicyConfig.load`).
_DEFAULT_DENIED_COMMAND_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/(?:\s|$)",
    r"rm\s+-rf\s+~(?:\s|/|$)",
    r"rm\s+-rf\s+\*",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # shell fork bomb
    r"\bdrop\s+(table|database)\b",
    r"\btruncate\s+table\b",
    r"chmod\s+-R\s+777\s+/",
    r"\bmkfs\.",
    r">\s*/dev/sd[a-z]\b",
    r"\bgit\s+push\s+(--force|-f)\b[^|;&]*\b(origin\s+)?(main|master)\b",
    r"\bgit\s+branch\s+-D\s+(main|master)\b",
]

_DEFAULT_APPROVAL_COMMAND_PATTERNS: List[str] = [
    r"\bgit\s+push\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-f",
    r"\bnpm\s+publish\b",
    r"\bpip\s+install\b.*--upgrade",
    r"\bsudo\b",
    r"\bcurl\b.*\|\s*(sh|bash)\b",
]

_DEFAULT_PROTECTED_PATH_PATTERNS: List[str] = [
    ".env", ".env.*", "**/.env", "**/.env.*",
    "**/credentials*", "**/*secret*", "**/*.pem", "**/id_rsa*",
    "**/.ssh/**", "**/.aws/**", "**/.git/**",
]


class PolicyVerdict(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class ActionRequest:
    """The reconstructed, already-known facts about one agent action, as
    the caller understands it *before* running it -- Golden Boy does not
    intercept tool calls itself; a caller builds this from whatever it
    already knows (the tool name, the command it's about to run, the
    file(s) it's about to touch, an `Estimator`-derived cost, and its own
    running session/day totals)."""

    tool: str
    command: Optional[str] = None
    file_paths: List[str] = field(default_factory=list)
    estimated_cost_percentage: float = 0.0
    session_calls_for_tool: int = 0
    session_spent_percentage: float = 0.0
    day_spent_percentage: float = 0.0
    task_type: Optional[str] = None


@dataclass
class PolicyResult:
    verdict: PolicyVerdict
    check: str          # "permission" | "budget" | "risk" | "scope" | "none"
    reason_code: str
    reason: str
    matched_rule: Optional[str] = None

    @property
    def allowed(self) -> bool:
        return self.verdict == PolicyVerdict.ALLOW


def _validate_patterns(name: str, patterns: List[str]) -> List[str]:
    for p in patterns:
        try:
            re.compile(p)
        except re.error as e:
            raise PolicyError(f"policy config field '{name}' has an invalid pattern {p!r}: {e}") from e
    return patterns


@dataclass
class PolicyConfig:
    """Policy Engine thresholds and rule lists. Same override cascade as
    `GoldenBoyConfig` (constructor arg > env var > `.goldenboy/policy.json`
    > built-in default), but rule lists (patterns/paths) are wholesale
    *replaced* by a JSON file's value when present, not merged -- a
    project's policy file is expected to be the full, intentional rule set,
    not a diff against Golden Boy's own defaults.

    Attributes:
        denied_tools: Tool names never allowed to run at all.
        approval_required_tools: Tool names that always require approval,
            regardless of cost or command.
        denied_command_patterns: Regex patterns (case-insensitive) that, if
            found in `ActionRequest.command`, cause an outright DENY.
        approval_command_patterns: Regex patterns that require approval
            (checked only if no denied pattern matched first).
        protected_path_patterns: Glob-style patterns (supporting a leading
            `**/`) that, if any `ActionRequest.file_paths` entry matches,
            cause an outright DENY.
        max_calls_per_session_per_tool: Hard cap on how many times one tool
            may be requested in a session before further calls are denied.
            `None` disables this check.
        session_budget_limit_percentage: Hard cap on cumulative estimated
            cost (this request's estimate plus `session_spent_percentage`)
            for a session. `None` disables this check.
        day_budget_limit_percentage: Same, for a calendar day. `None`
            disables this check.
        max_single_action_cost_percentage: A single request estimated above
            this fraction of budget requires approval (not an outright
            deny -- a legitimately large task should still be approvable).

    Raises:
        PolicyError: if constructed with an invalid regex pattern, or
            loaded from a config file that isn't a JSON object.
    """

    denied_tools: List[str] = field(default_factory=list)
    approval_required_tools: List[str] = field(default_factory=list)
    denied_command_patterns: List[str] = field(
        default_factory=lambda: list(_DEFAULT_DENIED_COMMAND_PATTERNS)
    )
    approval_command_patterns: List[str] = field(
        default_factory=lambda: list(_DEFAULT_APPROVAL_COMMAND_PATTERNS)
    )
    protected_path_patterns: List[str] = field(
        default_factory=lambda: list(_DEFAULT_PROTECTED_PATH_PATTERNS)
    )
    max_calls_per_session_per_tool: Optional[int] = 50
    session_budget_limit_percentage: Optional[float] = None
    day_budget_limit_percentage: Optional[float] = None
    max_single_action_cost_percentage: float = 40.0

    def __post_init__(self) -> None:
        _validate_patterns("denied_command_patterns", self.denied_command_patterns)
        _validate_patterns("approval_command_patterns", self.approval_command_patterns)
        if self.max_calls_per_session_per_tool is not None and self.max_calls_per_session_per_tool < 1:
            raise PolicyError("max_calls_per_session_per_tool must be >= 1 or None.")
        if not (0.0 <= self.max_single_action_cost_percentage <= 100.0):
            raise PolicyError("max_single_action_cost_percentage must be within [0, 100].")

    @classmethod
    def load(cls, config_path: str = ".goldenboy/policy.json") -> "PolicyConfig":
        """Defaults, then a JSON file if present. A missing file is not an
        error (falls back to defaults, same as `GoldenBoyConfig.load`); a
        *present but broken* file raises `PolicyError` rather than
        silently ignoring a policy someone intentionally set."""
        values: Dict[str, object] = {}
        valid_keys = {f for f in cls.__dataclass_fields__}

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_values = json.load(f)
            except json.JSONDecodeError as e:
                raise PolicyError(
                    f"Could not parse policy file at '{config_path}': {e}. "
                    "Fix the JSON syntax, or remove the file to use defaults."
                ) from e
            except OSError as e:
                raise PolicyError(f"Could not read policy file at '{config_path}': {e}") from e

            if not isinstance(file_values, dict):
                raise PolicyError(
                    f"Policy file at '{config_path}' must contain a JSON object, "
                    f"got {type(file_values).__name__}."
                )
            unknown = sorted(set(file_values) - valid_keys)
            if unknown:
                raise PolicyError(
                    f"Policy file at '{config_path}' has unknown key(s): {', '.join(unknown)} "
                    f"(valid keys: {', '.join(sorted(valid_keys))})."
                )
            values.update(file_values)

        for numeric_field in (
            "max_calls_per_session_per_tool",
            "session_budget_limit_percentage",
            "day_budget_limit_percentage",
            "max_single_action_cost_percentage",
        ):
            raw = os.getenv(_ENV_PREFIX + numeric_field.upper())
            if raw is None:
                continue
            try:
                values[numeric_field] = float(raw) if "." in raw or numeric_field.endswith(
                    "_percentage"
                ) else int(raw)
            except ValueError as e:
                raise PolicyError(
                    f"Environment variable {_ENV_PREFIX + numeric_field.upper()}={raw!r} "
                    "is not a valid number."
                ) from e

        return cls(**values)  # type: ignore[arg-type]


def _path_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if pattern.startswith("**/"):
        suffix = pattern[3:]
        parts = normalized.split("/")
        return any(
            fnmatch.fnmatch("/".join(parts[i:]), suffix) or fnmatch.fnmatch(parts[i], suffix)
            for i in range(len(parts))
        )
    return fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(os.path.basename(normalized), pattern)


class PolicyEngine:
    """Evaluates one `ActionRequest` against a `PolicyConfig` and returns a
    `PolicyResult`. Stateless aside from its config/audit store -- safe to
    construct once and reuse across requests within a process."""

    def __init__(self, config: Optional[PolicyConfig] = None, audit_store=None):
        self.config = config or PolicyConfig.load()
        self.audit_store = audit_store
        self._denied_command_re = [re.compile(p, re.IGNORECASE) for p in self.config.denied_command_patterns]
        self._approval_command_re = [
            re.compile(p, re.IGNORECASE) for p in self.config.approval_command_patterns
        ]

    def _check_permission(self, request: ActionRequest) -> Optional[PolicyResult]:
        if request.tool in self.config.denied_tools:
            return PolicyResult(
                PolicyVerdict.DENY, "permission", "TOOL_DENIED",
                f"Tool '{request.tool}' is on the denied-tools list.",
                matched_rule=request.tool,
            )
        if request.tool in self.config.approval_required_tools:
            return PolicyResult(
                PolicyVerdict.REQUIRE_APPROVAL, "permission", "TOOL_REQUIRES_APPROVAL",
                f"Tool '{request.tool}' always requires approval.",
                matched_rule=request.tool,
            )
        return None

    def _check_budget(self, request: ActionRequest) -> Optional[PolicyResult]:
        cfg = self.config
        if (
            cfg.max_calls_per_session_per_tool is not None
            and request.session_calls_for_tool >= cfg.max_calls_per_session_per_tool
        ):
            return PolicyResult(
                PolicyVerdict.DENY, "budget", "SESSION_CALL_LIMIT_EXCEEDED",
                f"Tool '{request.tool}' has been called {request.session_calls_for_tool} time(s) "
                f"this session, at or above the limit of {cfg.max_calls_per_session_per_tool}.",
            )
        if cfg.session_budget_limit_percentage is not None:
            projected = request.session_spent_percentage + request.estimated_cost_percentage
            if projected > cfg.session_budget_limit_percentage:
                return PolicyResult(
                    PolicyVerdict.DENY, "budget", "SESSION_BUDGET_EXCEEDED",
                    f"This request would bring session spend to {projected:.1f}%, "
                    f"above the session limit of {cfg.session_budget_limit_percentage:.1f}%.",
                )
        if cfg.day_budget_limit_percentage is not None:
            projected = request.day_spent_percentage + request.estimated_cost_percentage
            if projected > cfg.day_budget_limit_percentage:
                return PolicyResult(
                    PolicyVerdict.DENY, "budget", "DAILY_BUDGET_EXCEEDED",
                    f"This request would bring today's spend to {projected:.1f}%, "
                    f"above the daily limit of {cfg.day_budget_limit_percentage:.1f}%.",
                )
        if request.estimated_cost_percentage > cfg.max_single_action_cost_percentage:
            return PolicyResult(
                PolicyVerdict.REQUIRE_APPROVAL, "budget", "SINGLE_ACTION_COST_ABOVE_THRESHOLD",
                f"Estimated cost {request.estimated_cost_percentage:.1f}% exceeds the "
                f"single-action approval threshold of {cfg.max_single_action_cost_percentage:.1f}%.",
            )
        return None

    def _check_risk(self, request: ActionRequest) -> Optional[PolicyResult]:
        if not request.command:
            return None
        for pattern, compiled in zip(self.config.denied_command_patterns, self._denied_command_re):
            if compiled.search(request.command):
                return PolicyResult(
                    PolicyVerdict.DENY, "risk", "DANGEROUS_COMMAND",
                    f"Command matches a denied pattern ({pattern!r}).",
                    matched_rule=pattern,
                )
        for pattern, compiled in zip(self.config.approval_command_patterns, self._approval_command_re):
            if compiled.search(request.command):
                return PolicyResult(
                    PolicyVerdict.REQUIRE_APPROVAL, "risk", "COMMAND_REQUIRES_APPROVAL",
                    f"Command matches a pattern requiring approval ({pattern!r}).",
                    matched_rule=pattern,
                )
        return None

    def _check_scope(self, request: ActionRequest) -> Optional[PolicyResult]:
        for path in request.file_paths:
            for pattern in self.config.protected_path_patterns:
                if _path_matches(path, pattern):
                    return PolicyResult(
                        PolicyVerdict.DENY, "scope", "PROTECTED_PATH",
                        f"Path '{path}' matches protected pattern {pattern!r}.",
                        matched_rule=pattern,
                    )
        return None

    def evaluate(self, request: ActionRequest, task_id: Optional[str] = None) -> PolicyResult:
        result = (
            self._check_permission(request)
            or self._check_budget(request)
            or self._check_risk(request)
            or self._check_scope(request)
            or PolicyResult(PolicyVerdict.ALLOW, "none", "ALLOWED", "All policy checks passed.")
        )

        if self.audit_store is not None:
            self._record(request, result, task_id)
        return result

    def _record(self, request: ActionRequest, result: PolicyResult, task_id: Optional[str]) -> None:
        from goldenboy.core.audit import AuditEntry  # local import: audit.py doesn't need governance.py

        outcome = {
            PolicyVerdict.ALLOW: "success",
            PolicyVerdict.DENY: "blocked",
            PolicyVerdict.REQUIRE_APPROVAL: "pending_approval",
        }[result.verdict]
        entry = AuditEntry.create(
            action="policy_check",
            result=outcome,
            task_id=task_id,
            tool=request.tool,
            decision=result.verdict.value,
            policy_result=result.reason_code,
            estimated_cost=request.estimated_cost_percentage,
        )
        self.audit_store.record(entry)

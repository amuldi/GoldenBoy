"""Golden Boy: a budget/workload optimization layer for AI coding agents.

Public API — small and deliberate. Anything not listed here (e.g. CLI
internals in `goldenboy.cli`, or specific provider adapters) is available
by importing its submodule directly, but isn't guaranteed stable between
minor versions the way this top-level API is.

Notably absent: `AnthropicAdapter` / `OpenAIAdapter`. Importing them
requires the `anthropic`/`openai` optional extras — keeping them out of
`goldenboy/__init__.py` means `import goldenboy` never requires either.
Import them explicitly when you need them:

    from goldenboy.adapters.anthropic_adapter import AnthropicAdapter
    from goldenboy.adapters.openai_adapter import OpenAIAdapter
"""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from goldenboy.adapters.base import ProviderAdapter
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.audit import AuditEntry, AuditStore
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.decision_engine import DecisionEngine
from goldenboy.core.errors import (
    CheckpointError,
    ConfigError,
    GoldenBoyError,
    PolicyError,
    SnapshotError,
)
from goldenboy.core.estimator import Estimator, TaskEstimate
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.failure_memory import FailureMemoryStore, FailureRecord
from goldenboy.core.governance import (
    ActionRequest,
    PolicyConfig,
    PolicyEngine,
    PolicyResult,
    PolicyVerdict,
)
from goldenboy.core.heartbeat import HeartbeatResult
from goldenboy.core.history import HistoryStore, TaskEvent
from goldenboy.core.loop_detection import LoopCheckResult, LoopDetector
from goldenboy.core.policies import (
    ComplexityOnlyPolicy,
    FixedThresholdPolicy,
    GoldenBoyPolicy,
    Policy,
    PolicyDecision,
    UsageOnlyPolicy,
)
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import ExecutionMode, RiskEngine
from goldenboy.core.router import ModelRouter, ModelTier, RouterConfig, RoutingDecision
from goldenboy.core.snapshot import Snapshot, SnapshotManager, VerifyResult
from goldenboy.core.spending import LedgerSummary, SessionMarker, SpendEntry, SpendingStore
from goldenboy.core.task_classifier import TaskClassifier
from goldenboy.core.task_types import DecisionAction, TaskType
from goldenboy.integration import budget_aware_execution
from goldenboy.protocol import GoldenBoyDecision, ProtocolError

try:
    __version__ = _version("goldenboy")
except PackageNotFoundError:  # running from source without an installed/editable metadata record
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    # Config
    "GoldenBoyConfig",
    # Budget / usage semantics
    "Budget",
    "UsageConfidence",
    # Risk
    "ExecutionMode",
    "RiskEngine",
    # Estimation
    "Estimator",
    "TaskEstimate",
    # Work model
    "Priority",
    "ExecutionUnit",
    # Execution
    "AdaptiveExecutor",
    "budget_aware_execution",
    # Adapters (provider-specific ones live in their own submodules — see above)
    "ProviderAdapter",
    "MockProvider",
    # Persistence
    "CheckpointManager",
    # Task intelligence
    "TaskType",
    "TaskClassifier",
    "DecisionAction",
    "DecisionEngine",
    # Protocol (the stable, versioned decision contract)
    "GoldenBoyDecision",
    "ProtocolError",
    # History / local learning data
    "HistoryStore",
    "TaskEvent",
    # Baseline + Golden Boy policies (used by goldenboy.replay)
    "Policy",
    "PolicyDecision",
    "FixedThresholdPolicy",
    "ComplexityOnlyPolicy",
    "UsageOnlyPolicy",
    "GoldenBoyPolicy",
    # Policy Engine (agent-action governance — distinct from the replay
    # baselines above; see goldenboy.core.governance)
    "PolicyEngine",
    "PolicyConfig",
    "ActionRequest",
    "PolicyResult",
    "PolicyVerdict",
    # Budget ledger (session/day spend tracking, in absolute tokens)
    "SpendingStore",
    "SpendEntry",
    "LedgerSummary",
    "SessionMarker",
    # Model Router
    "ModelRouter",
    "RouterConfig",
    "RoutingDecision",
    "ModelTier",
    # Audit Log
    "AuditStore",
    "AuditEntry",
    # Checkpoint / rollback of working-tree changes (git-based; distinct
    # from CheckpointManager's task-plan checkpoint above)
    "SnapshotManager",
    "Snapshot",
    "VerifyResult",
    # Loop detection
    "LoopDetector",
    "LoopCheckResult",
    # Failure memory
    "FailureMemoryStore",
    "FailureRecord",
    # Heartbeat (experimental — see README.md)
    "HeartbeatResult",
    # Errors
    "GoldenBoyError",
    "ConfigError",
    "CheckpointError",
    "PolicyError",
    "SnapshotError",
]

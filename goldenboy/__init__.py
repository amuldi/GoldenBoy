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
from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.errors import CheckpointError, ConfigError, GoldenBoyError
from goldenboy.core.estimator import Estimator, TaskEstimate
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import ExecutionMode, RiskEngine
from goldenboy.integration import budget_aware_execution

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
    # Errors
    "GoldenBoyError",
    "ConfigError",
    "CheckpointError",
]

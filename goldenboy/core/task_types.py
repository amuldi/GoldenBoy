"""Task type and decision-action vocabularies shared by the task classifier,
the decision engine, and the protocol layer."""
from enum import Enum


class TaskType(Enum):
    IMPLEMENTATION = "implementation"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    TESTING = "testing"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    DEPENDENCY_CHANGE = "dependency_change"
    ARCHITECTURE_CHANGE = "architecture_change"
    CODE_REVIEW = "code_review"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    RELEASE = "release"
    UNKNOWN = "unknown"


class DecisionAction(Enum):
    """The vocabulary a `GoldenBoyDecision.action` is drawn from.

    Distinct from `ExecutionMode` (SAFE/CAUTION/LIMITED/CRITICAL, a *risk*
    classification): this is the concrete recommendation `DecisionEngine`
    derives from that risk plus task type and progress.
    """

    RUN = "run"                    # Start the task normally; nothing has happened yet.
    CONTINUE = "continue"          # Keep going as planned; budget/risk still comfortable.
    REDUCE_SCOPE = "reduce_scope"  # Keep going, but only on higher-priority remaining work.
    FINISH = "finish"              # Wrap up the essential remainder now, then stop.
    VERIFY = "verify"              # Implementation looks done; run verification, then stop.
    STOP = "stop"                  # Checkpoint and stop; budget cannot cover more work.
    ASK_USER = "ask_user"          # Confidence is too low to recommend an action safely.

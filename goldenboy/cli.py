import importlib.util
import logging
import os
import sys
from argparse import ArgumentParser

from goldenboy.adapters.mock import MockProvider
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.estimator import Estimator
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import RiskEngine

_TASK_DISPLAY_LIMIT = 100  # display-only truncation; the full text still drives the estimate


def create_example_plan():
    """An illustrative plan used by the CLI demo commands.

    Golden Boy does not (yet) decompose an arbitrary natural-language task
    into concrete ExecutionUnits automatically — that requires an agent's
    own reasoning (see skills/goldenboy/SKILL.md for the prompt-level
    approach, or define ExecutionUnits yourself via the Python API for a
    real plan). This fixed example exists only to demonstrate how a plan
    is *adapted* once a risk mode is known; the units below don't come
    from whatever task string you pass to `plan`/`run`.
    """
    return [
        ExecutionUnit("1", "Core feature implementation", Priority.P0, estimated_cost=10.0),
        ExecutionUnit("2", "Critical integration tests", Priority.P1, estimated_cost=8.0),
        ExecutionUnit("3", "Secondary cleanup", Priority.P2, estimated_cost=5.0),
        ExecutionUnit("4", "Animations / visual polish", Priority.P3, estimated_cost=4.0),
        ExecutionUnit("5", "Full documentation pass", Priority.P4, estimated_cost=6.0),
    ]


def _display_task(task: str) -> str:
    """Truncate only for terminal display; the estimate is always computed
    from the full, untruncated task text."""
    if len(task) <= _TASK_DISPLAY_LIMIT:
        return task
    return task[:_TASK_DISPLAY_LIMIT].rstrip() + "…"


def _require_nonblank_task(task: str, command: str) -> None:
    if not task.strip():
        print(
            f"error: '{command}' needs a non-empty task description "
            f"(got {task!r}). Example: goldenboy {command} \"Add OAuth login\"",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _print_budget(budget):
    if budget.confidence.value == "EXACT":
        confidence_note = ""
    else:
        confidence_note = f" ({budget.confidence.value.lower()}, source: {budget.source})"
    print(f"Remaining Budget: {budget.remaining_percentage:.2f}%{confidence_note}")


def status_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    budget = provider.get_available_budget()

    print("--- Golden Boy Status ---")
    _print_budget(budget)
    if budget.is_exhausted():
        print("State: EXHAUSTED (Below safety margin)")
    else:
        print(f"Usable Budget:    {budget.usable_percentage:.2f}%")

    cm = CheckpointManager()
    cp = cm.load()
    if cp:
        print(f"\nCheckpoint found for task: '{cp['task_name']}' (mode: {cp['mode']})")
        if cp.get("created_at"):
            print(f"  Saved at: {cp['created_at']}")
        deferred = [u for u in cp["plan"] if u.status == "deferred"]
        print(f"  Deferred units: {len(deferred)}")
        if cp.get("next_recommended_action"):
            print(f"  Next: {cp['next_recommended_action']}")


def plan_cmd(args):
    _require_nonblank_task(args.task, "plan")
    provider = MockProvider(initial_percentage=args.budget)
    budget = provider.get_available_budget()

    # Real, task-text-driven estimate (this is the number that changes
    # with what you actually typed — the example plan below does not).
    estimator = Estimator()
    task_estimate = estimator.estimate_task(args.task)

    plan = create_example_plan()
    risk_engine = RiskEngine()
    mode = risk_engine.assess(budget, task_estimate)

    print(f"--- Execution Plan: '{_display_task(args.task)}' ---")
    _print_budget(budget)
    print(
        f"Estimated Cost (heuristic, based on prompt + repo size): "
        f"{task_estimate.estimated_percentage:.2f}% (confidence: {task_estimate.confidence:.2f})"
    )
    print(f"Risk Assessment: {mode.name}\n")

    print("Example unit breakdown (illustrative, not derived from the task above):")
    for unit in plan:
        print(f"  [{unit.priority.name}] {unit.description} (Cost: {unit.estimated_cost}%)")


def run_cmd(args):
    _require_nonblank_task(args.task, "run")
    provider = MockProvider(initial_percentage=args.budget)
    executor = AdaptiveExecutor(provider)

    plan = create_example_plan()

    print(f"Starting Task: '{_display_task(args.task)}'")
    print(
        "Note: this uses the illustrative example plan (see 'goldenboy plan --help'); "
        "it does not decompose the task text above into real units."
    )
    result_msg, final_plan = executor.execute(args.task, plan)

    print("\n--- Result ---")
    print(result_msg)
    print("\nDeferred Work:")
    deferred = [u for u in final_plan if u.status == "deferred"]
    if not deferred:
        print("  None.")
    for d in deferred:
        print(f"  - [{d.priority.name}] {d.description}")


def resume_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    executor = AdaptiveExecutor(provider)

    cm = CheckpointManager()
    state = cm.load()

    if not state:
        print("No checkpoint found.")
        return

    task_name = state["task_name"]
    plan = state["plan"]

    if not any(u.status == "deferred" for u in plan):
        print(f"Checkpoint for '{task_name}' has no deferred units — nothing to resume.")
        return

    # Reset deferred tasks to pending for resume
    for unit in plan:
        if unit.status == "deferred":
            unit.status = "pending"

    print(f"Resuming Task: '{task_name}'")
    result_msg, final_plan = executor.execute(task_name, plan)

    print("\n--- Resume Result ---")
    print(result_msg)


def doctor_cmd(args):
    """Real, verifiable diagnostics only — no invented health score. Each
    line reports something actually checked; nothing here is simulated."""
    print("--- Golden Boy Doctor ---")
    print(f"Python: {sys.version.split()[0]}")

    # (extra name, importable module, env var to check presence of -- never
    # printed, only whether it's set)
    _providers = (
        ("tiktoken", "tiktoken", None, None),
        ("anthropic", "anthropic", "ANTHROPIC_API_KEY", "Anthropic"),
        ("openai", "openai", "OPENAI_API_KEY", "OpenAI"),
    )
    for extra, module_name, env_var, display_name in _providers:
        installed = importlib.util.find_spec(module_name) is not None
        print(f"Optional dependency '{extra}': {'installed' if installed else 'not installed'}")
        if installed and env_var:
            # Presence only -- never print the key's value.
            configured = bool(os.getenv(env_var))
            label = "configured" if configured else f"not configured ({env_var} not set)"
            print(f"  {display_name} API key: {label}")

    try:
        config = GoldenBoyConfig.load()
        print(
            "Config: OK "
            f"(safety_margin={config.safety_margin}, caution_ratio={config.caution_ratio}, "
            f"base_cost_per_unit={config.base_cost_per_unit}, max_budget_tokens={config.max_budget_tokens}, "
            f"stale_after_seconds={config.stale_after_seconds})"
        )
    except GoldenBoyError as e:
        print(f"Config: ERROR — {e}")

    cm = CheckpointManager()
    if not os.path.exists(cm.checkpoint_file):
        print("Checkpoint: none present")
    else:
        try:
            state = cm.load()
            deferred = len([u for u in state["plan"] if u.status == "deferred"])
            print(f"Checkpoint: OK — task '{state['task_name']}', {deferred} unit(s) deferred")
        except GoldenBoyError as e:
            print(f"Checkpoint: ERROR — {e}")


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Golden Boy - Budget-Aware Execution Layer")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show internal INFO/WARNING logs (budget checks, per-unit execution) alongside output.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    p_status = subparsers.add_parser("status", help="Show current budget state and any pending checkpoint")
    p_status.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_plan = subparsers.add_parser("plan", help="Estimate a task's cost and show the resulting risk mode")
    p_plan.add_argument("task", type=str, help="The task to analyze")
    p_plan.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_run = subparsers.add_parser("run", help="Execute the example plan adaptively (demo)")
    p_run.add_argument("task", type=str, help="A label for the run (see 'plan' for a task-driven estimate)")
    p_run.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_resume = subparsers.add_parser("resume", help="Resume the previous checkpoint")
    p_resume.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    subparsers.add_parser(
        "doctor", help="Check Python version, optional dependencies, config, and checkpoint state"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="[%(name)s] %(message)s",
    )

    try:
        if args.command == "status":
            status_cmd(args)
        elif args.command == "plan":
            plan_cmd(args)
        elif args.command == "run":
            run_cmd(args)
        elif args.command == "resume":
            resume_cmd(args)
        elif args.command == "doctor":
            doctor_cmd(args)
        else:
            parser.print_help()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

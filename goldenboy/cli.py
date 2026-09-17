import importlib.util
import json as json_module
import logging
import os
import sys
from argparse import ArgumentParser
from dataclasses import asdict

from goldenboy.adapters.mock import MockProvider
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze as run_analytics
from goldenboy.core.benchmark import run_all as run_benchmark
from goldenboy.core.calibration import calibrate
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.decision_engine import DecisionEngine
from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.estimator import Estimator
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.history import HistoryStore
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import RiskEngine
from goldenboy.core.telemetry import (
    VALID_OUTCOMES,
    VALID_VERIFICATION_STATUSES,
    ExecutionTelemetry,
    TelemetryStore,
)
from goldenboy.replay.engine import run_backtest

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

    if getattr(args, "json", False):
        cm = CheckpointManager()
        cp = cm.load()
        payload = {
            "remaining_percentage": budget.remaining_percentage,
            "usable_percentage": budget.usable_percentage,
            "is_exhausted": budget.is_exhausted(),
            "source": budget.source,
            "confidence": budget.confidence.value,
            "checkpoint": (
                {
                    "task_name": cp["task_name"],
                    "mode": cp["mode"],
                    "deferred_units": len([u for u in cp["plan"] if u.status == "deferred"]),
                }
                if cp
                else None
            ),
        }
        print(json_module.dumps(payload, indent=2))
        return

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
        f"Estimated Cost (heuristic, based on prompt + relevant repo context + expected output): "
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
    as_json = getattr(args, "json", False)
    if not as_json:
        print("--- Golden Boy Doctor ---")
        print(f"Python: {sys.version.split()[0]}")

    # (extra name, importable module, env var to check presence of -- never
    # printed, only whether it's set)
    _providers = (
        ("tiktoken", "tiktoken", None, None),
        ("anthropic", "anthropic", "ANTHROPIC_API_KEY", "Anthropic"),
        ("openai", "openai", "OPENAI_API_KEY", "OpenAI"),
    )
    dependencies = {}
    for extra, module_name, env_var, display_name in _providers:
        installed = importlib.util.find_spec(module_name) is not None
        entry = {"installed": installed}
        if not as_json:
            print(f"Optional dependency '{extra}': {'installed' if installed else 'not installed'}")
        if installed and env_var:
            # Presence only -- never print/export the key's value.
            configured = bool(os.getenv(env_var))
            entry["api_key_configured"] = configured
            if not as_json:
                label = "configured" if configured else f"not configured ({env_var} not set)"
                print(f"  {display_name} API key: {label}")
        dependencies[extra] = entry

    try:
        config = GoldenBoyConfig.load()
        config_ok = True
        config_detail = {
            "safety_margin": config.safety_margin, "caution_ratio": config.caution_ratio,
            "base_cost_per_unit": config.base_cost_per_unit, "max_budget_tokens": config.max_budget_tokens,
            "stale_after_seconds": config.stale_after_seconds,
        }
        if not as_json:
            print(
                "Config: OK "
                f"(safety_margin={config.safety_margin}, caution_ratio={config.caution_ratio}, "
                f"base_cost_per_unit={config.base_cost_per_unit}, "
                f"max_budget_tokens={config.max_budget_tokens}, "
                f"stale_after_seconds={config.stale_after_seconds})"
            )
    except GoldenBoyError as e:
        config_ok = False
        config_detail = str(e)
        if not as_json:
            print(f"Config: ERROR — {e}")

    cm = CheckpointManager()
    checkpoint_ok = True
    checkpoint_detail = "none present"
    if os.path.exists(cm.checkpoint_file):
        try:
            state = cm.load()
            deferred = len([u for u in state["plan"] if u.status == "deferred"])
            checkpoint_detail = f"OK — task '{state['task_name']}', {deferred} unit(s) deferred"
            if not as_json:
                print(f"Checkpoint: {checkpoint_detail}")
        except GoldenBoyError as e:
            checkpoint_ok = False
            checkpoint_detail = str(e)
            if not as_json:
                print(f"Checkpoint: ERROR — {e}")
    elif not as_json:
        print("Checkpoint: none present")

    if as_json:
        payload = {
            "python": sys.version.split()[0],
            "dependencies": dependencies,
            "config": {"ok": config_ok, "detail": config_detail},
            "checkpoint": {"ok": checkpoint_ok, "detail": checkpoint_detail},
        }
        print(json_module.dumps(payload, indent=2))


def _history_store_for(dataset_path):
    """Resolve a HistoryStore for either the default local log
    (`.goldenboy/history.jsonl`) or an explicit `--dataset` file path --
    same on-disk format, just pointed elsewhere, so no separate loader is
    needed for an exported/shared JSONL file."""
    if not dataset_path:
        return HistoryStore()
    directory = os.path.dirname(dataset_path) or "."
    filename = os.path.basename(dataset_path)
    return HistoryStore(history_dir=directory, filename=filename)


def analyze_cmd(args):
    _require_nonblank_task(args.task, "analyze")
    if args.progress is not None and not (0.0 <= args.progress <= 1.0):
        print(
            f"error: 'analyze' --progress must be within [0.0, 1.0] (got {args.progress!r}).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    provider = MockProvider(initial_percentage=args.budget)
    engine = DecisionEngine()
    decision = engine.decide(args.task, provider, progress=args.progress)

    if args.json:
        print(decision.to_json())
        return

    if not args.quiet:
        print(f"--- Golden Boy Analysis: '{_display_task(args.task)}' ---")
    print(
        f"Task type:        {decision.task.task_type} "
        f"(confidence: {decision.task.task_type_confidence:.2f})"
    )
    if decision.task.secondary_task_types:
        print(f"Also detected:    {', '.join(decision.task.secondary_task_types)}")
    print(f"Complexity:       {decision.task.complexity_label} ({decision.task.complexity:.2f})")
    if decision.task.complexity_signals:
        print(f"Complexity signals: {', '.join(decision.task.complexity_signals)}")
    print(
        f"Estimated cost:   {decision.task.estimated_cost_percentage:.2f}% "
        f"(confidence: {decision.task.estimated_cost_confidence:.2f})"
    )
    print(
        f"Remaining usage:  {decision.usage.remaining_percentage:.2f}% "
        f"({decision.usage.confidence.lower()}, source: {decision.usage.source})"
    )
    print(f"Risk:             {decision.risk.mode} ({decision.risk.reason_code})")
    print(f"Decision:         {decision.action.upper()} (confidence: {decision.confidence:.2f})")
    print(f"Reason:           {decision.reason}")
    if decision.recommendation:
        print("Recommendation:")
        for step in decision.recommendation:
            print(f"  - {step}")


def validate_cmd(args):
    exit_code = 0

    try:
        config = GoldenBoyConfig.load()
        config_ok = True
        config_detail = (
            f"safety_margin={config.safety_margin}, caution_ratio={config.caution_ratio}, "
            f"base_cost_per_unit={config.base_cost_per_unit}, max_budget_tokens={config.max_budget_tokens}, "
            f"stale_after_seconds={config.stale_after_seconds}"
        )
    except GoldenBoyError as e:
        config_ok = False
        config_detail = str(e)
        exit_code = 1

    cm = CheckpointManager()
    checkpoint_ok = True
    checkpoint_detail = "none present"
    if os.path.exists(cm.checkpoint_file):
        try:
            state = cm.load()
            deferred = len([u for u in state["plan"] if u.status == "deferred"])
            checkpoint_detail = f"task '{state['task_name']}', {deferred} unit(s) deferred"
        except GoldenBoyError as e:
            checkpoint_ok = False
            checkpoint_detail = str(e)
            exit_code = 1

    report = data_quality.validate(HistoryStore())
    if report.status == "POOR":
        exit_code = 1

    if args.json:
        payload = {
            "config": {"ok": config_ok, "detail": config_detail},
            "checkpoint": {"ok": checkpoint_ok, "detail": checkpoint_detail},
            "history_quality": asdict(report),
        }
        print(json_module.dumps(payload, indent=2))
    else:
        if not args.quiet:
            print("--- Golden Boy Validate ---")
        print(f"Config:     {'OK' if config_ok else 'ERROR'} — {config_detail}")
        print(f"Checkpoint: {'OK' if checkpoint_ok else 'ERROR'} — {checkpoint_detail}")
        print()
        print(report.render())

    if exit_code:
        raise SystemExit(exit_code)


def replay_cmd(args):
    store = _history_store_for(args.dataset)
    result = store.load_events()
    report = run_backtest(result.events)

    if args.json:
        payload = {
            "dataset_size": report.dataset_size,
            "corrupted_lines": result.corrupted_lines,
            "policies": [asdict(m) for m in report.policies],
            "limitations": report.limitations,
        }
        print(json_module.dumps(payload, indent=2))
        return

    if not args.quiet and result.corrupted_lines:
        print(f"Note: {result.corrupted_lines} corrupted line(s) skipped while loading the dataset.\n")
    print(report.render())


def _telemetry_store_for(dataset_path):
    """Same resolution rule as `_history_store_for`, for
    `.goldenboy/telemetry.jsonl` (or an explicit `--dataset` file)."""
    if not dataset_path:
        return TelemetryStore()
    directory = os.path.dirname(dataset_path) or "."
    filename = os.path.basename(dataset_path)
    return TelemetryStore(history_dir=directory, filename=filename)


def report_cmd(args):
    """Records one `ExecutionTelemetry` event -- what an external agent
    actually observed after acting on a prior `goldenboy analyze` decision.
    See `goldenboy.core.telemetry` for the full field contract and why
    every field but `--outcome` is optional."""
    if args.json_file:
        try:
            with open(args.json_file, "r", encoding="utf-8") as f:
                data = json_module.load(f)
        except OSError as e:
            print(f"error: could not read '{args.json_file}': {e}", file=sys.stderr)
            raise SystemExit(1)
        except json_module.JSONDecodeError as e:
            print(f"error: '{args.json_file}' is not valid JSON: {e}", file=sys.stderr)
            raise SystemExit(1)
        if "final_outcome" not in data:
            print("error: telemetry JSON file is missing required field 'final_outcome'", file=sys.stderr)
            raise SystemExit(1)
        # schema_version/recorded_at/actual_cost_percentage are set by
        # create() itself (the last is derived, not an input) -- dropped
        # here so a file that happens to be a previously-recorded event's
        # own to_dict() output can still be re-ingested.
        _derived_only = ("schema_version", "recorded_at", "actual_cost_percentage")
        kwargs = {k: v for k, v in data.items() if k not in _derived_only}
    else:
        if not args.outcome:
            print("error: 'report' requires either --outcome or --json-file", file=sys.stderr)
            raise SystemExit(1)
        kwargs = dict(
            final_outcome=args.outcome,
            verification_status=args.verification_status,
            failure_reason=args.failure_reason,
            task_id=args.task_id,
            execution_id=args.execution_id,
            task_type=args.task_type,
            estimated_cost_percentage=args.estimated_cost_percentage,
            estimated_cost_confidence=args.estimated_cost_confidence,
            actual_input_tokens=args.actual_input_tokens,
            actual_output_tokens=args.actual_output_tokens,
            actual_total_tokens=args.actual_total_tokens,
            actual_cost_usd=args.actual_cost_usd,
            duration_seconds=args.duration_seconds,
            tool_calls=args.tool_calls,
            files_touched=args.files_touched,
            lines_added=args.lines_added,
            lines_removed=args.lines_removed,
            tests_run=args.tests_run,
            tests_passed=args.tests_passed,
            tests_failed=args.tests_failed,
            retry_count=args.retry_count,
        )

    try:
        event = ExecutionTelemetry.create(**kwargs)
    except (ValueError, TypeError) as e:
        print(f"error: invalid telemetry: {e}", file=sys.stderr)
        raise SystemExit(1)

    TelemetryStore().append(event)

    if args.json:
        print(json_module.dumps(event.to_dict(), indent=2))
    elif not args.quiet:
        detail = f"outcome={event.final_outcome}"
        if event.verification_status:
            detail += f", verification={event.verification_status}"
        if event.actual_cost_percentage is not None:
            detail += f", actual_cost={event.actual_cost_percentage:.2f}%"
        print(f"Recorded telemetry: {detail}")


def calibrate_cmd(args):
    store = _telemetry_store_for(args.dataset)
    result = store.load_events()
    report = calibrate(result.events)

    if args.json:
        payload = {
            "sample_count": len(result.events),
            "corrupted_lines": result.corrupted_lines,
            "excluded_missing_data": report.excluded_missing_data,
            "overall": asdict(report.overall),
            "by_task_type": {k: asdict(v) for k, v in report.by_task_type.items()},
        }
        print(json_module.dumps(payload, indent=2))
        return

    if not args.quiet and result.corrupted_lines:
        print(f"Note: {result.corrupted_lines} corrupted line(s) skipped while loading the dataset.\n")
    print(report.render())


def benchmark_cmd(args):
    report = run_benchmark()
    if args.json:
        payload = asdict(report)
        print(json_module.dumps(payload, indent=2))
        return
    print(report.render())


def export_cmd(args):
    cm = CheckpointManager()
    checkpoint_state = None
    if os.path.exists(cm.checkpoint_file):
        try:
            state = cm.load()
            checkpoint_state = {
                "task_name": state["task_name"],
                "mode": state["mode"],
                "created_at": state.get("created_at"),
                "units": [
                    {
                        "id": u.id, "description": u.description,
                        "priority": u.priority.name, "status": u.status,
                    }
                    for u in state["plan"]
                ],
            }
        except GoldenBoyError:
            checkpoint_state = None

    config = GoldenBoyConfig.load()
    store = HistoryStore()
    load_result = store.load_events()
    quality = data_quality.validate(store)
    analytics_report = run_analytics(store)

    payload = {
        "config": asdict(config),
        "checkpoint": checkpoint_state,
        "history": {
            "quality": asdict(quality),
            "analytics": asdict(analytics_report),
            "events": [e.to_dict() for e in load_result.events],
        },
    }

    text = json_module.dumps(payload, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        if not args.quiet:
            print(f"Exported to {args.output}")
    else:
        print(text)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Golden Boy - Budget-Aware Execution Layer")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show internal INFO/WARNING logs (budget checks, per-unit execution) alongside output.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    p_status = subparsers.add_parser("status", help="Show current budget state and any pending checkpoint")
    p_status.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    p_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")

    p_plan = subparsers.add_parser("plan", help="Estimate a task's cost and show the resulting risk mode")
    p_plan.add_argument("task", type=str, help="The task to analyze")
    p_plan.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_run = subparsers.add_parser("run", help="Execute the example plan adaptively (demo)")
    p_run.add_argument("task", type=str, help="A label for the run (see 'plan' for a task-driven estimate)")
    p_run.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_resume = subparsers.add_parser("resume", help="Resume the previous checkpoint")
    p_resume.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    p_doctor = subparsers.add_parser(
        "doctor", help="Check Python version, optional dependencies, config, and checkpoint state"
    )
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")

    p_analyze = subparsers.add_parser(
        "analyze", help="Full task-intelligence decision: type, complexity, risk, action, and why"
    )
    p_analyze.add_argument("task", type=str, help="The task to analyze")
    p_analyze.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    p_analyze.add_argument(
        "--progress", type=float, default=None,
        help="Reported progress on the task, 0.0-1.0 (omit if genuinely unknown)",
    )
    p_analyze.add_argument("--json", action="store_true", help="Emit the GoldenBoyDecision protocol payload")
    p_analyze.add_argument("--quiet", action="store_true", help="Suppress the header banner")

    p_validate = subparsers.add_parser(
        "validate", help="Validate config, checkpoint, and local history data quality"
    )
    p_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    p_validate.add_argument("--quiet", action="store_true", help="Suppress the header banner")

    p_replay = subparsers.add_parser(
        "replay", help="Backtest baseline policies against recorded (or exported) history"
    )
    p_replay.add_argument(
        "--dataset", type=str, default=None,
        help="Path to a history JSONL file (default: this project's .goldenboy/history.jsonl)",
    )
    p_replay.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a table")
    p_replay.add_argument("--quiet", action="store_true", help="Suppress non-essential notes")

    p_report = subparsers.add_parser(
        "report",
        help="Record actual execution telemetry for a task Golden Boy previously analyzed",
    )
    p_report.add_argument(
        "--outcome", type=str, default=None, choices=sorted(VALID_OUTCOMES),
        help="What the execution concluded with (required unless --json-file is given)",
    )
    p_report.add_argument(
        "--verification-status", dest="verification_status", type=str, default=None,
        choices=sorted(VALID_VERIFICATION_STATUSES),
        help="Whether the outcome was actually backed by collected evidence (e.g. a real test run)",
    )
    p_report.add_argument("--failure-reason", dest="failure_reason", type=str, default=None)
    p_report.add_argument("--task-id", dest="task_id", type=str, default=None)
    p_report.add_argument("--execution-id", dest="execution_id", type=str, default=None)
    p_report.add_argument(
        "--task-type", dest="task_type", type=str, default=None,
        help="Echo of the task_type from the original 'goldenboy analyze' decision, for calibration",
    )
    p_report.add_argument(
        "--estimated-cost-percentage", dest="estimated_cost_percentage", type=float, default=None,
        help="Echo of estimated_cost_percentage from the original 'goldenboy analyze' decision",
    )
    p_report.add_argument(
        "--estimated-cost-confidence", dest="estimated_cost_confidence", type=float, default=None,
    )
    p_report.add_argument("--actual-input-tokens", dest="actual_input_tokens", type=int, default=None)
    p_report.add_argument("--actual-output-tokens", dest="actual_output_tokens", type=int, default=None)
    p_report.add_argument(
        "--actual-total-tokens", dest="actual_total_tokens", type=int, default=None,
        help="Used with --estimated-cost-percentage to compute calibration error",
    )
    p_report.add_argument("--actual-cost-usd", dest="actual_cost_usd", type=float, default=None)
    p_report.add_argument("--duration-seconds", dest="duration_seconds", type=float, default=None)
    p_report.add_argument("--tool-calls", dest="tool_calls", type=int, default=None)
    p_report.add_argument("--files-touched", dest="files_touched", type=int, default=None)
    p_report.add_argument("--lines-added", dest="lines_added", type=int, default=None)
    p_report.add_argument("--lines-removed", dest="lines_removed", type=int, default=None)
    p_report.add_argument("--tests-run", dest="tests_run", type=int, default=None)
    p_report.add_argument("--tests-passed", dest="tests_passed", type=int, default=None)
    p_report.add_argument("--tests-failed", dest="tests_failed", type=int, default=None)
    p_report.add_argument("--retry-count", dest="retry_count", type=int, default=None)
    p_report.add_argument(
        "--json-file", dest="json_file", type=str, default=None,
        help="Read the full telemetry record from a JSON file instead of the flags above",
    )
    p_report.add_argument("--json", action="store_true", help="Emit the recorded record as JSON")
    p_report.add_argument("--quiet", action="store_true", help="Suppress the confirmation line")

    p_calibrate = subparsers.add_parser(
        "calibrate",
        help="Compare estimated vs. actual cost (MAE/RMSE/bias) over recorded execution telemetry",
    )
    p_calibrate.add_argument(
        "--dataset", type=str, default=None,
        help="Path to a telemetry JSONL file (default: this project's .goldenboy/telemetry.jsonl)",
    )
    p_calibrate.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    p_calibrate.add_argument("--quiet", action="store_true", help="Suppress non-essential notes")

    p_benchmark = subparsers.add_parser(
        "benchmark", help="Measure estimator/risk-engine/CLI-startup latency on this machine, now"
    )
    p_benchmark.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")

    p_export = subparsers.add_parser(
        "export", help="Export config, checkpoint, and history as one reproducible JSON document"
    )
    p_export.add_argument("--output", type=str, default=None, help="Write to this path instead of stdout")
    p_export.add_argument("--quiet", action="store_true", help="Suppress the 'Exported to ...' confirmation")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    quiet = getattr(args, "quiet", False)
    if quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    logging.basicConfig(level=log_level, format="[%(name)s] %(message)s")

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
        elif args.command == "analyze":
            analyze_cmd(args)
        elif args.command == "validate":
            validate_cmd(args)
        elif args.command == "replay":
            replay_cmd(args)
        elif args.command == "report":
            report_cmd(args)
        elif args.command == "calibrate":
            calibrate_cmd(args)
        elif args.command == "benchmark":
            benchmark_cmd(args)
        elif args.command == "export":
            export_cmd(args)
        else:
            parser.print_help()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

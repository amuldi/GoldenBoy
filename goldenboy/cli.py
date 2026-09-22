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
from goldenboy.core.audit import AuditStore
from goldenboy.core.benchmark import run_all as run_benchmark
from goldenboy.core.budget import Budget
from goldenboy.core.calibration import calibrate
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.decision_engine import DecisionEngine
from goldenboy.core.errors import GoldenBoyError
from goldenboy.core.estimator import Estimator
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.failure_memory import FailureCategory, FailureMemoryStore
from goldenboy.core.governance import ActionRequest, PolicyConfig, PolicyEngine, PolicyVerdict
from goldenboy.core.heartbeat import check as heartbeat_check
from goldenboy.core.history import HistoryStore
from goldenboy.core.loop_detection import LoopDetector
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import ExecutionMode, RiskEngine
from goldenboy.core.risk_budget import RiskBudgetConfig, RiskBudgetEngine, RiskBudgetError
from goldenboy.core.router import ModelRouter, RouterConfig
from goldenboy.core.snapshot import SnapshotError, SnapshotManager
from goldenboy.core.spending import (
    SessionMarker,
    SpendEntry,
    SpendingStore,
    filter_since,
    filter_today,
    summarize,
)
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


def policy_cmd(args):
    try:
        config = PolicyConfig.load(args.policy_file) if args.policy_file else PolicyConfig.load()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)

    audit_store = AuditStore() if args.audit else None
    engine = PolicyEngine(config=config, audit_store=audit_store)
    request = ActionRequest(
        tool=args.tool,
        command=args.shell_command,
        file_paths=args.paths,
        estimated_cost_percentage=args.estimated_cost_percentage,
        session_calls_for_tool=args.session_calls,
        session_spent_percentage=args.session_spent_percentage,
        day_spent_percentage=args.day_spent_percentage,
    )
    result = engine.evaluate(request, task_id=args.task_id)

    if args.json:
        payload = {
            "verdict": result.verdict.value,
            "check": result.check,
            "reason_code": result.reason_code,
            "reason": result.reason,
            "matched_rule": result.matched_rule,
        }
        print(json_module.dumps(payload, indent=2))
    else:
        print(f"Verdict: {result.verdict.value.upper()}")
        print(f"Check:   {result.check}")
        print(f"Reason:  {result.reason} ({result.reason_code})")
        if result.matched_rule:
            print(f"Matched: {result.matched_rule}")

    if result.verdict == PolicyVerdict.DENY:
        raise SystemExit(1)
    if result.verdict == PolicyVerdict.REQUIRE_APPROVAL:
        raise SystemExit(2)


def route_cmd(args):
    _require_nonblank_task(args.task, "route")
    provider = MockProvider(initial_percentage=args.budget)
    engine = DecisionEngine()
    decision = engine.decide(args.task, provider)

    try:
        router_config = RouterConfig.load(args.router_file) if args.router_file else RouterConfig.load()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)
    router = ModelRouter(config=router_config)
    routing = router.route(decision.task.complexity_label, ExecutionMode(decision.risk.mode))

    if args.json:
        print(json_module.dumps(routing.to_dict(), indent=2))
        return

    if not args.quiet:
        print(f"--- Golden Boy Model Router: '{_display_task(args.task)}' ---")
    print(f"Complexity:   {routing.complexity_label} -> tier '{routing.complexity_tier.value}'")
    print(f"Budget risk:  {routing.execution_mode} -> cap '{routing.budget_cap_tier.value}'")
    print(f"Routed tier:  {routing.tier.value.upper()}")
    model_note = routing.model_name or (
        "(unconfigured — map tiers to real model names in .goldenboy/router.json)"
    )
    print(f"Model:        {model_note}")
    print(f"Reason:       {routing.reason}")


def audit_cmd(args):
    store = AuditStore()
    result = store.load_events()
    entries = result.events[-args.limit:] if args.limit > 0 else result.events

    if args.json:
        payload = {
            "total_lines": result.total_lines,
            "corrupted_lines": result.corrupted_lines,
            "entries": [e.to_dict() for e in entries],
        }
        print(json_module.dumps(payload, indent=2))
        return

    if not entries:
        print("No audit entries recorded yet.")
        return
    for i, entry in enumerate(entries):
        if i:
            print()
        print(entry.render())


def spend_cmd(args):
    store = SpendingStore()
    marker = SessionMarker()

    if args.action == "reset-session":
        started = marker.reset()
        if args.json:
            print(json_module.dumps({"session_start": started}, indent=2))
        else:
            print(f"Session reset. New session start: {started}")
        return

    if args.action == "record":
        if args.label is None or args.estimated_tokens is None:
            print("error: 'spend record' requires --label and --estimated-tokens", file=sys.stderr)
            raise SystemExit(1)
        try:
            entry = SpendEntry.create(
                label=args.label,
                estimated_tokens=args.estimated_tokens,
                actual_tokens=args.actual_tokens,
                task_type=args.task_type,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)
        store.append(entry)

    result = store.load_events()
    if args.window == "session":
        entries = filter_since(result.entries, marker.get_or_create())
    elif args.window == "daily":
        entries = filter_today(result.entries)
    else:
        entries = result.entries

    ledger = summarize(entries, limit_tokens=args.budget_limit, window=args.window)

    if args.json:
        print(json_module.dumps(asdict(ledger), indent=2))
    else:
        print(ledger.render())

    if ledger.over_limit:
        raise SystemExit(1)


def snapshot_cmd(args):
    mgr = SnapshotManager(repo_dir=args.repo_dir)

    if args.action == "create":
        try:
            snap = mgr.create(label=args.label)
        except SnapshotError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)
        if args.json:
            print(json_module.dumps(snap.to_dict(), indent=2))
        else:
            state = "clean tree" if snap.clean else "dirty tree captured"
            print(f"Snapshot {snap.id} created ({state}) at HEAD {snap.head_sha[:12]}.")
        return

    if args.action == "list":
        snaps = mgr.list()
        if args.json:
            print(json_module.dumps([s.to_dict() for s in snaps], indent=2))
            return
        if not snaps:
            print("No snapshots recorded yet.")
            return
        for s in snaps:
            print(f"{s.id}  {s.created_at}  {'clean' if s.clean else 'dirty'}  {s.label}")
        return

    if args.action == "verify":
        if not args.checks:
            print("error: 'snapshot verify' requires at least one --check", file=sys.stderr)
            raise SystemExit(1)
        result = mgr.verify(args.checks)
        if args.json:
            print(json_module.dumps(asdict(result), indent=2))
        else:
            print(result.render())

        if not result.passed:
            if args.rollback_on_fail:
                try:
                    target = mgr.rollback()
                    print(f"Rolled back to snapshot {target.id}.")
                except SnapshotError as e:
                    print(f"error: rollback failed: {e}", file=sys.stderr)
            raise SystemExit(1)
        return

    if args.action == "rollback":
        target = None
        if args.snapshot_id:
            target = mgr.get(args.snapshot_id)
            if target is None:
                print(f"error: no snapshot with id '{args.snapshot_id}'", file=sys.stderr)
                raise SystemExit(1)
        try:
            restored = mgr.rollback(target)
        except SnapshotError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)
        if args.json:
            print(json_module.dumps(restored.to_dict(), indent=2))
        else:
            print(f"Rolled back to snapshot {restored.id} ({restored.label}).")


def loop_cmd(args):
    detector = LoopDetector(threshold=args.threshold)

    if args.action == "reset":
        detector.reset()
        if args.json:
            print(json_module.dumps({"reset": True}, indent=2))
        else:
            print("Loop-detection state cleared.")
        return

    if args.action == "status":
        entries = detector.status()
        if args.json:
            print(json_module.dumps({sig: asdict(e) for sig, e in entries.items()}, indent=2))
            return
        if not entries:
            print("No tracked signatures.")
            return
        for e in entries.values():
            print(
                f"{e.tool}: count={e.count} "
                f"(signature={e.signature}, first={e.first_seen}, last={e.last_seen})"
            )
        return

    if args.action == "record":
        if not args.tool:
            print("error: 'loop record' requires --tool", file=sys.stderr)
            raise SystemExit(1)
        result = detector.record(args.tool, args.args_summary, args.error_summary)
        if args.json:
            print(json_module.dumps(asdict(result), indent=2))
        else:
            print(f"Signature {result.signature} ({result.tool}): {result.count}/{result.threshold}")
            print(result.recommendation)
        if result.should_stop:
            raise SystemExit(1)


def failure_cmd(args):
    store = FailureMemoryStore()

    if args.action == "record":
        if not args.cause:
            print("error: 'failure record' requires --cause", file=sys.stderr)
            raise SystemExit(1)
        category = None
        if args.category:
            try:
                category = FailureCategory(args.category)
            except ValueError:
                valid = ", ".join(c.value for c in FailureCategory)
                print(f"error: --category must be one of: {valid}", file=sys.stderr)
                raise SystemExit(1)
        record = store.record(args.cause, task_type=args.task_type, category=category)
        if args.json:
            print(json_module.dumps(record.to_dict(), indent=2))
        else:
            print(
                f"Recorded (signature={record.signature}, attempt_count={record.attempt_count}, "
                f"category={record.category})."
            )
        return

    if args.action == "resolve":
        if not args.signature or not args.resolution:
            print("error: 'failure resolve' requires --signature and --resolution", file=sys.stderr)
            raise SystemExit(1)
        record = store.resolve(args.signature, args.resolution)
        if record is None:
            print(f"error: no failure record with signature '{args.signature}'", file=sys.stderr)
            raise SystemExit(1)
        if args.json:
            print(json_module.dumps(record.to_dict(), indent=2))
        else:
            print(f"Marked resolved (signature={record.signature}).")
        return

    if args.action == "list":
        records = store.load_all()
        if args.json:
            print(json_module.dumps([r.to_dict() for r in records], indent=2))
            return
        if not records:
            print("No failure records yet.")
            return
        for r in records:
            status = "resolved" if r.resolved else "open"
            print(f"{r.signature}  attempts={r.attempt_count}  [{status}]  ({r.category})  {r.cause_summary}")
        return

    if args.action == "similar":
        if not args.cause:
            print("error: 'failure similar' requires --cause", file=sys.stderr)
            raise SystemExit(1)
        similar = store.find_similar(args.cause, min_similarity=args.min_similarity)
        if args.json:
            payload = [{"similarity": s.similarity, "record": s.record.to_dict()} for s in similar]
            print(json_module.dumps(payload, indent=2))
            return
        if not similar:
            print("No similar past failures found.")
            return
        for s in similar:
            print(
                f"[{s.similarity:.2f}] {s.record.signature}  "
                f"attempts={s.record.attempt_count}  {s.record.cause_summary}"
            )


def risk_cmd(args):
    try:
        config = RiskBudgetConfig.load(args.config_file) if args.config_file else RiskBudgetConfig.load()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)
    engine = RiskBudgetEngine(config=config)

    if args.action == "reset":
        engine.reset()
        if args.json:
            print(json_module.dumps({"reset": True}, indent=2))
        else:
            print("Risk budget reset to initial value.")
        return

    if args.action == "status":
        state = engine.status()
        if args.json:
            print(json_module.dumps(state.to_dict(), indent=2))
            return
        print(f"Remaining risk budget: {state.remaining:.1f} (of {config.initial_budget:.1f})")
        print(f"Operations recorded:   {state.operations_recorded}")
        print(f"Total deducted:        {state.total_deducted:.1f}")
        if state.last_operation:
            print(f"Last operation:        {state.last_operation} (at {state.last_updated})")
        return

    if args.action == "record":
        if not args.operation:
            print("error: 'risk record' requires --operation", file=sys.stderr)
            raise SystemExit(1)
        try:
            result = engine.record(args.operation, repeat_count=args.repeat_count)
        except (ValueError, RiskBudgetError) as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1)

        if args.json:
            print(json_module.dumps(result.to_dict(), indent=2))
        else:
            print(f"Verdict:  {result.verdict.value.upper()}")
            print(f"Weight:   -{result.weight_applied:.1f} (operation: {result.operation})")
            print(f"Remaining: {result.remaining:.1f}")
            print(f"Reason:   {result.reason}")

        if result.verdict == PolicyVerdict.DENY:
            raise SystemExit(1)
        if result.verdict == PolicyVerdict.REQUIRE_APPROVAL:
            raise SystemExit(2)


def trace_cmd(args):
    store = AuditStore()
    entries = store.trace(args.task_id)

    if args.json:
        payload = {"task_id": args.task_id, "entries": [e.to_dict() for e in entries]}
        print(json_module.dumps(payload, indent=2))
        return

    if not entries:
        print(f"No audit entries recorded for task_id '{args.task_id}'.")
        return
    print(f"--- Execution Trace: '{args.task_id}' ({len(entries)} event(s)) ---")
    for i, entry in enumerate(entries):
        if i:
            print()
        print(entry.render())


def heartbeat_cmd(args):
    budget_obj = None
    if args.budget is not None:
        budget_obj = Budget(remaining_percentage=args.budget, source="cli")

    result = heartbeat_check(budget=budget_obj, previous_budget_percentage=args.previous_budget)

    if args.json:
        print(json_module.dumps(asdict(result), indent=2))
        return

    print(f"Should wake: {result.should_wake}")
    for reason in result.reasons:
        print(f"  - {reason}")


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

    p_policy = subparsers.add_parser(
        "policy", help="Policy Engine: evaluate one action (ALLOW/DENY/REQUIRE_APPROVAL), code-enforced"
    )
    p_policy.add_argument(
        "tool", type=str, help="Tool/action name being requested (e.g. 'bash', 'file_write')"
    )
    p_policy.add_argument(
        "--command", dest="shell_command", type=str, default=None,
        help="Shell command text, if this action runs one",
    )
    p_policy.add_argument(
        "--path", dest="paths", action="append", default=[],
        help="A file path this action touches (repeatable)",
    )
    p_policy.add_argument("--estimated-cost-percentage", type=float, default=0.0)
    p_policy.add_argument(
        "--session-calls", type=int, default=0,
        help="How many times this tool has already been called this session",
    )
    p_policy.add_argument("--session-spent-percentage", type=float, default=0.0)
    p_policy.add_argument("--day-spent-percentage", type=float, default=0.0)
    p_policy.add_argument(
        "--policy-file", type=str, default=None,
        help="Path to a policy config JSON file (default: .goldenboy/policy.json)",
    )
    p_policy.add_argument("--task-id", type=str, default=None)
    p_policy.add_argument("--audit", action="store_true", help="Also record this decision to the audit log")
    p_policy.add_argument("--json", action="store_true")

    p_route = subparsers.add_parser(
        "route", help="Model Router: map task complexity + budget risk to a provider-neutral tier"
    )
    p_route.add_argument("task", type=str, help="The task to route")
    p_route.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    p_route.add_argument(
        "--router-file", type=str, default=None,
        help="Path to a router config JSON file mapping tiers to real model names "
        "(default: .goldenboy/router.json)",
    )
    p_route.add_argument("--json", action="store_true")
    p_route.add_argument("--quiet", action="store_true", help="Suppress the header banner")

    p_audit = subparsers.add_parser("audit", help="Show recent Audit Log entries")
    p_audit.add_argument("--limit", type=int, default=20, help="Show at most this many recent entries")
    p_audit.add_argument("--json", action="store_true")

    p_spend = subparsers.add_parser(
        "spend", help="Budget ledger: record/inspect session- and day-level token spend against a limit"
    )
    p_spend.add_argument("action", choices=["record", "status", "reset-session"])
    p_spend.add_argument("--label", type=str, default=None, help="Required for 'record'")
    p_spend.add_argument("--task-type", type=str, default=None)
    p_spend.add_argument("--estimated-tokens", type=int, default=None, help="Required for 'record'")
    p_spend.add_argument("--actual-tokens", type=int, default=None)
    p_spend.add_argument(
        "--budget-limit", type=int, default=None,
        help="Token limit for the reported window; omit to report totals without an enforced limit",
    )
    p_spend.add_argument("--window", choices=["session", "daily", "all"], default="session")
    p_spend.add_argument("--json", action="store_true")

    p_snapshot = subparsers.add_parser(
        "snapshot",
        help="Git-based checkpoint/verify/rollback of working-tree changes "
        "(distinct from the task-plan checkpoint shown by 'goldenboy status')",
    )
    p_snapshot.add_argument("action", choices=["create", "verify", "rollback", "list"])
    p_snapshot.add_argument("--label", type=str, default="")
    p_snapshot.add_argument(
        "--check", dest="checks", action="append", default=[],
        help="A command to run for 'verify' (repeatable, e.g. --check 'pytest tests/' --check mypy)",
    )
    p_snapshot.add_argument(
        "--id", dest="snapshot_id", type=str, default=None,
        help="Snapshot id for 'rollback' (default: latest)",
    )
    p_snapshot.add_argument(
        "--rollback-on-fail", action="store_true",
        help="With 'verify': automatically roll back to the latest snapshot if verification fails",
    )
    p_snapshot.add_argument("--repo-dir", type=str, default=".")
    p_snapshot.add_argument("--json", action="store_true")

    p_loop = subparsers.add_parser(
        "loop",
        help="Loop detection: record an attempt and check whether the same signature repeated too often",
    )
    p_loop.add_argument("action", choices=["record", "status", "reset"])
    p_loop.add_argument("--tool", type=str, default=None, help="Required for 'record'")
    p_loop.add_argument(
        "--args", dest="args_summary", type=str, default="", help="Short summary of the arguments used"
    )
    p_loop.add_argument(
        "--error", dest="error_summary", type=str, default="",
        help="Short summary of the resulting error, if any",
    )
    p_loop.add_argument(
        "--threshold", type=int, default=None, help="Override GoldenBoyConfig.loop_repeat_threshold"
    )
    p_loop.add_argument("--json", action="store_true")

    p_failure = subparsers.add_parser(
        "failure", help="Failure memory: record/list/resolve/find-similar past task failures"
    )
    p_failure.add_argument("action", choices=["record", "list", "resolve", "similar"])
    p_failure.add_argument("--cause", type=str, default=None, help="Required for 'record' and 'similar'")
    p_failure.add_argument("--task-type", dest="task_type", type=str, default=None)
    p_failure.add_argument("--signature", type=str, default=None, help="Required for 'resolve'")
    p_failure.add_argument("--resolution", type=str, default=None, help="Required for 'resolve'")
    p_failure.add_argument(
        "--min-similarity", type=float, default=0.4, help="Threshold for 'similar' (0.0-1.0)"
    )
    p_failure.add_argument(
        "--category", type=str, default=None,
        choices=[c.value for c in FailureCategory],
        help="Override the auto-classified category for 'record' (default: classified from --cause)",
    )
    p_failure.add_argument("--json", action="store_true")

    p_risk = subparsers.add_parser(
        "risk",
        help="Risk Budget: cumulative point-based risk accounting, distinct from budget/policy "
        "(record an operation, check status, or reset the session)",
    )
    p_risk.add_argument("action", choices=["record", "status", "reset"])
    p_risk.add_argument("--operation", type=str, default=None, help="Required for 'record'")
    p_risk.add_argument(
        "--repeat-count", dest="repeat_count", type=int, default=1,
        help="How many times this same signature has now occurred (e.g. from 'goldenboy loop record' "
        "or a failure's attempt_count) -- repeats beyond the first cost extra, per config",
    )
    p_risk.add_argument(
        "--config-file", dest="config_file", type=str, default=None,
        help="Path to a risk-budget config JSON file (default: .goldenboy/risk_budget.json)",
    )
    p_risk.add_argument("--json", action="store_true")

    p_trace = subparsers.add_parser(
        "trace",
        help="Execution Trace: every recorded Audit Log entry for one task, in order "
        "(distinct from 'goldenboy audit', which shows recent entries unfiltered)",
    )
    p_trace.add_argument("task_id", type=str, help="The task_id to trace")
    p_trace.add_argument("--json", action="store_true")

    p_heartbeat = subparsers.add_parser(
        "heartbeat",
        help="Experimental: cheap local check for whether anything needs attention "
        "(no LLM call, not a background daemon — see README.md)",
    )
    p_heartbeat.add_argument(
        "--budget", type=float, default=None, help="Current remaining budget percentage, if known"
    )
    p_heartbeat.add_argument(
        "--previous-budget", dest="previous_budget", type=float, default=None,
        help="The remaining budget percentage as of the last check, to detect a change",
    )
    p_heartbeat.add_argument("--json", action="store_true")

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
        elif args.command == "policy":
            policy_cmd(args)
        elif args.command == "route":
            route_cmd(args)
        elif args.command == "audit":
            audit_cmd(args)
        elif args.command == "spend":
            spend_cmd(args)
        elif args.command == "snapshot":
            snapshot_cmd(args)
        elif args.command == "loop":
            loop_cmd(args)
        elif args.command == "failure":
            failure_cmd(args)
        elif args.command == "risk":
            risk_cmd(args)
        elif args.command == "trace":
            trace_cmd(args)
        elif args.command == "heartbeat":
            heartbeat_cmd(args)
        else:
            parser.print_help()
    except GoldenBoyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

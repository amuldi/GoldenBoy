"""End-to-end CLI tests for the analyze/validate/replay/benchmark/export
commands -- same argv -> main() -> stdout/exit-code style as test_cli.py."""
import json

import pytest

from goldenboy.cli import main
from goldenboy.core.history import HistoryStore, TaskEvent


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["goldenboy"] + argv)
    main()


def _seed_history(n=12):
    store = HistoryStore()
    for i in range(n):
        store.append(
            TaskEvent.create(
                task_text=f"Fix a bug {i}",
                task_type="bug_fix",
                task_type_confidence=0.8,
                priority="P1",
                estimated_cost_percentage=10.0,
                estimated_cost_confidence=0.85,
                usage_source="mock",
                usage_confidence="EXACT",
                remaining_usage_start=60.0,
                decision_mode="SAFE",
                outcome="completed" if i % 3 else "failed",
            )
        )
    return store


# --- analyze ----------------------------------------------------------------

def test_analyze_prints_a_decision(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["analyze", "Fix a bug in the login flow", "--budget", "50"])
    out = capsys.readouterr().out
    assert "Task type:" in out
    assert "Decision:" in out
    assert "Reason:" in out


def test_analyze_json_round_trips_through_the_protocol(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["analyze", "Refactor the checkout module", "--budget", "80", "--json"])
    out = capsys.readouterr().out

    from goldenboy.protocol import GoldenBoyDecision

    decision = GoldenBoyDecision.from_json(out)
    assert decision.task.task_type == "refactor"


def test_analyze_rejects_empty_task(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["analyze", "", "--budget", "50"])
    assert exc_info.value.code == 1
    assert "non-empty task" in capsys.readouterr().err


def test_analyze_rejects_out_of_range_progress(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["analyze", "Fix a bug", "--progress", "1.5"])
    assert exc_info.value.code == 1
    assert "progress" in capsys.readouterr().err


def test_analyze_quiet_suppresses_the_banner(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["analyze", "Fix a bug", "--budget", "50", "--quiet"])
    out = capsys.readouterr().out
    assert "--- Golden Boy Analysis" not in out


# --- validate -----------------------------------------------------------------

def test_validate_reports_no_data_on_fresh_install(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["validate"])
    out = capsys.readouterr().out
    assert "NO_DATA" in out


def test_validate_json_is_well_formed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["validate", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "config" in payload
    assert "checkpoint" in payload
    assert "history_quality" in payload


def test_validate_exits_nonzero_on_broken_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOLDENBOY_CAUTION_RATIO", "5.0")
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["validate"])
    assert exc_info.value.code == 1


def test_validate_checkpoint_line_has_no_duplicated_ok_prefix(tmp_path, monkeypatch, capsys):
    """Regression test: validate_cmd used to print 'Checkpoint: OK — OK —
    task ...' because CheckpointManager's own success string already
    started with 'OK — ' and the CLI added a second one on top."""
    monkeypatch.chdir(tmp_path)
    from goldenboy.core.checkpoint import CheckpointManager
    from goldenboy.core.priorities import ExecutionUnit, Priority

    plan = [ExecutionUnit("1", "Still pending", Priority.P1, status="deferred")]
    CheckpointManager().save("Demo", plan, "LIMITED")

    _run(monkeypatch, ["validate"])
    out = capsys.readouterr().out
    assert "OK — OK" not in out
    assert "Checkpoint: OK — task 'Demo'" in out


# --- replay ---------------------------------------------------------------

def test_replay_reports_na_below_minimum_events(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["replay"])
    out = capsys.readouterr().out
    assert "N/A" in out


def test_replay_scores_policies_against_seeded_history(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_history(12)

    _run(monkeypatch, ["replay"])
    out = capsys.readouterr().out
    assert "golden_boy_risk_engine" in out
    assert "Limitations:" in out


def test_replay_json_is_well_formed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_history(12)

    _run(monkeypatch, ["replay", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_size"] == 12
    assert len(payload["policies"]) == 5


def test_replay_against_explicit_dataset_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    dataset_dir = tmp_path / "exported"
    dataset_dir.mkdir()
    store = HistoryStore(history_dir=str(dataset_dir), filename="my_history.jsonl")
    for i in range(12):
        store.append(
            TaskEvent.create(
                task_text=f"task {i}", task_type="bug_fix", task_type_confidence=0.8,
                priority="P1", estimated_cost_percentage=10.0, estimated_cost_confidence=0.85,
                usage_source="mock", usage_confidence="EXACT", remaining_usage_start=60.0,
                decision_mode="SAFE", outcome="completed",
            )
        )

    _run(monkeypatch, ["replay", "--dataset", str(dataset_dir / "my_history.jsonl")])
    out = capsys.readouterr().out
    assert "Backtest over 12" in out


# --- benchmark --------------------------------------------------------------

def test_benchmark_json_is_well_formed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["benchmark", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "python_version" in payload
    assert "platform" in payload


def test_benchmark_text_mentions_estimator(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["benchmark"])
    out = capsys.readouterr().out
    assert "Estimator" in out


# --- export -----------------------------------------------------------------

def test_export_to_stdout_is_well_formed_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_history(3)

    _run(monkeypatch, ["export"])
    payload = json.loads(capsys.readouterr().out)
    assert "config" in payload
    assert "checkpoint" in payload
    assert len(payload["history"]["events"]) == 3


def test_export_never_includes_raw_task_text(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = HistoryStore()
    store.append(
        TaskEvent.create(
            task_text="a very specific secret prompt nobody should see exported",
            task_type="bug_fix", task_type_confidence=0.8, priority="P1",
            estimated_cost_percentage=10.0, estimated_cost_confidence=0.85,
            usage_source="mock", usage_confidence="EXACT", remaining_usage_start=60.0,
            decision_mode="SAFE", outcome="completed",
        )
    )

    _run(monkeypatch, ["export"])
    out = capsys.readouterr().out
    assert "secret prompt" not in out


def test_export_to_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out_path = tmp_path / "out.json"

    _run(monkeypatch, ["export", "--output", str(out_path)])
    assert out_path.exists()
    payload = json.loads(out_path.read_text())
    assert "config" in payload


def test_export_quiet_suppresses_confirmation(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out_path = tmp_path / "out.json"

    _run(monkeypatch, ["export", "--output", str(out_path), "--quiet"])
    assert capsys.readouterr().out == ""


# --- status/doctor --json ---------------------------------------------------

def test_status_json_is_well_formed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["status", "--budget", "42", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["remaining_percentage"] == 42.0
    assert payload["checkpoint"] is None


def test_doctor_json_is_well_formed_and_never_leaks_api_key(tmp_path, monkeypatch, capsys):
    pytest.importorskip("anthropic")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-appear")

    _run(monkeypatch, ["doctor", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert payload["dependencies"]["anthropic"]["api_key_configured"] is True
    assert "sk-ant-should-never-appear" not in out

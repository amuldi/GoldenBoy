"""End-to-end tests against goldenboy.cli.main() for the `report` and
`calibrate` commands -- the P0 estimate-vs-actual telemetry contract."""
import json

import pytest

from goldenboy.cli import main


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["goldenboy"] + argv)
    main()


def test_report_requires_outcome_or_json_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["report"])

    assert exc_info.value.code == 1
    assert "--outcome or --json-file" in capsys.readouterr().err


def test_report_from_flags_writes_to_telemetry_store(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _run(monkeypatch, [
        "report", "--outcome", "completed", "--verification-status", "VERIFIED",
        "--task-type", "bug_fix", "--estimated-cost-percentage", "5.0",
        "--actual-total-tokens", "4000", "--json",
    ])
    output = json.loads(capsys.readouterr().out)

    assert output["final_outcome"] == "completed"
    assert output["verification_status"] == "VERIFIED"
    assert output["actual_cost_percentage"] == 4.0

    from goldenboy.core.telemetry import TelemetryStore
    store = TelemetryStore()
    result = store.load_events()
    assert len(result.events) == 1
    assert result.events[0].task_type == "bug_fix"


def test_report_from_json_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / "telemetry.json"
    payload_path.write_text(
        json.dumps({
            "final_outcome": "failed",
            "verification_status": "FAILED",
            "failure_reason": "test regression",
            "actual_total_tokens": 30000,
        }),
        encoding="utf-8",
    )

    _run(monkeypatch, ["report", "--json-file", str(payload_path), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert output["final_outcome"] == "failed"
    assert output["failure_reason"] == "test regression"


def test_report_json_file_missing_final_outcome_is_a_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / "telemetry.json"
    payload_path.write_text(json.dumps({"tests_run": 3}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["report", "--json-file", str(payload_path)])

    assert exc_info.value.code == 1
    assert "final_outcome" in capsys.readouterr().err


def test_report_json_file_that_is_not_valid_json_is_a_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / "telemetry.json"
    payload_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["report", "--json-file", str(payload_path)])

    assert exc_info.value.code == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_calibrate_reports_na_with_no_telemetry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _run(monkeypatch, ["calibrate"])
    output = capsys.readouterr().out

    assert "N/A" in output


def test_calibrate_computes_real_metrics_once_enough_telemetry_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    for _ in range(10):
        _run(monkeypatch, [
            "report", "--outcome", "completed", "--task-type", "bug_fix",
            "--estimated-cost-percentage", "10.0", "--actual-total-tokens", "10000", "--quiet",
        ])
        capsys.readouterr()

    _run(monkeypatch, ["calibrate", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["sample_count"] == 10
    assert payload["overall"]["n"] == 10
    assert payload["overall"]["mae"] == 0.0
    assert payload["by_task_type"]["bug_fix"]["n"] == 10


def test_calibrate_dataset_flag_points_at_an_explicit_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    dataset_path = tmp_path / "exported-telemetry.jsonl"

    from goldenboy.core.telemetry import ExecutionTelemetry, TelemetryStore
    directory = str(dataset_path.parent)
    filename = dataset_path.name
    store = TelemetryStore(history_dir=directory, filename=filename)
    for _ in range(10):
        store.append(ExecutionTelemetry.create(
            final_outcome="completed", estimated_cost_percentage=10.0, actual_total_tokens=10_000,
        ))

    _run(monkeypatch, ["calibrate", "--dataset", str(dataset_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["sample_count"] == 10
    assert payload["overall"]["n"] == 10

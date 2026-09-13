"""End-to-end tests against goldenboy.cli.main() itself (not just the
library functions it calls) -- these are the tests that would have caught
the original "plan ignores the task text" bug and the "corrupted checkpoint
crashes with a raw traceback" bug, because they exercise the actual
argv -> main() -> stdout/exit-code path a real user hits.
"""
import re

import pytest

from goldenboy.cli import main


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["goldenboy"] + argv)
    main()


def _estimated_cost(output: str) -> float:
    match = re.search(r"Estimated Cost.*?:\s*([\d.]+)%", output)
    assert match, f"no 'Estimated Cost' line found in:\n{output}"
    return float(match.group(1))


def test_plan_produces_different_estimates_for_different_tasks(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # An empty tmp repo + the default 100_000-token normalizer would put both
    # prompts under the 5% floor and make them look identical for the wrong
    # reason (see test_estimator.py's version of this same comment). Lower
    # the normalizer so the real difference this test checks is visible.
    monkeypatch.setenv("GOLDENBOY_MAX_BUDGET_TOKENS", "200")

    _run(monkeypatch, ["plan", "Fix a typo in README", "--budget", "50"])
    small_output = capsys.readouterr().out

    _run(monkeypatch, [
        "plan",
        "Build an OAuth authentication system with refresh tokens and tests",
        "--budget", "50",
    ])
    large_output = capsys.readouterr().out

    assert "Fix a typo in README" in small_output
    assert "Build an OAuth authentication system" in large_output
    # The two task strings must not have produced identical estimates --
    # this is the regression test for the CLI ignoring task text entirely.
    assert _estimated_cost(small_output) != _estimated_cost(large_output)


def test_plan_rejects_empty_task(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["plan", "", "--budget", "50"])

    assert exc_info.value.code == 1
    assert "non-empty task" in capsys.readouterr().err


def test_plan_rejects_whitespace_only_task(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["plan", "   ", "--budget", "50"])

    assert exc_info.value.code == 1


def test_corrupted_checkpoint_produces_clean_error_not_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".goldenboy").mkdir()
    (tmp_path / ".goldenboy" / "checkpoint.json").write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["status", "--budget", "50"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "corrupted" in err
    assert "Traceback" not in err


def test_malformed_config_produces_clean_error_not_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".goldenboy").mkdir()
    (tmp_path / ".goldenboy" / "config.json").write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["status", "--budget", "50"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_out_of_range_config_value_produces_clean_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOLDENBOY_CAUTION_RATIO", "5.0")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["status", "--budget", "50"])

    assert exc_info.value.code == 1
    assert "caution_ratio" in capsys.readouterr().err


def test_resume_with_no_checkpoint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _run(monkeypatch, ["resume", "--budget", "50"])

    assert "No checkpoint found." in capsys.readouterr().out


def test_resume_when_checkpoint_has_nothing_deferred(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    from goldenboy.core.checkpoint import CheckpointManager
    from goldenboy.core.priorities import ExecutionUnit, Priority

    plan = [ExecutionUnit("1", "Already done", Priority.P0, status="completed")]
    CheckpointManager().save("Finished Task", plan, "SAFE")

    _run(monkeypatch, ["resume", "--budget", "50"])

    assert "nothing to resume" in capsys.readouterr().out


def test_run_executes_and_reports_deferred_work(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    # Example plan costs (10, 8, 5, 4, 6) total 33; budget=12 (margin 3 ->
    # usable 9) assesses LIMITED (required > usable), which defers P3/P4 up
    # front. P0 (cost 10) still fits the raw remaining (12) and completes,
    # which drops remaining to 2 -- <= the margin -- force-deferring P1/P2
    # mid-loop. Net: 1 completed, 4 deferred, deterministically.
    _run(monkeypatch, ["run", "demo task", "--budget", "12"])

    out = capsys.readouterr().out
    assert "Starting Task: 'demo task'" in out
    assert "Completed 1 units. Deferred 4 units." in out
    assert "[P1] Critical integration tests" in out  # listed under Deferred Work


def test_run_then_resume_completes_previously_deferred_units(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _run(monkeypatch, ["run", "demo task", "--budget", "12"])
    capsys.readouterr()

    # Resume with a full budget: everything previously deferred should
    # complete this time, and the checkpoint should end up cleared.
    _run(monkeypatch, ["resume", "--budget", "100"])
    resume_out = capsys.readouterr().out
    assert "Resuming Task: 'demo task'" in resume_out
    assert "Deferred 0 units" in resume_out

    _run(monkeypatch, ["status", "--budget", "100"])
    assert "Checkpoint found" not in capsys.readouterr().out


def test_doctor_reports_checkpoint_when_present(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from goldenboy.core.checkpoint import CheckpointManager
    from goldenboy.core.priorities import ExecutionUnit, Priority

    plan = [ExecutionUnit("1", "Still pending", Priority.P1, status="deferred")]
    CheckpointManager().save("Demo", plan, "LIMITED")

    _run(monkeypatch, ["doctor"])

    out = capsys.readouterr().out
    assert "Checkpoint: OK — task 'Demo', 1 unit(s) deferred" in out


def test_doctor_reports_api_key_configuration_without_leaking_the_value(tmp_path, monkeypatch, capsys):
    pytest.importorskip("anthropic")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-be-printed")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _run(monkeypatch, ["doctor"])

    out = capsys.readouterr().out
    assert "Anthropic API key: configured" in out
    assert "sk-ant-should-never-be-printed" not in out


def test_doctor_reports_checked_facts_without_crashing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _run(monkeypatch, ["doctor"])

    out = capsys.readouterr().out
    assert "Python:" in out
    assert "Config: OK" in out
    assert "Checkpoint: none present" in out


def test_invalid_command_is_an_argparse_usage_error(monkeypatch):
    monkeypatch.setattr("sys.argv", ["goldenboy", "not-a-real-command"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2  # argparse's own usage-error exit code


def test_missing_task_argument_is_an_argparse_usage_error(monkeypatch):
    monkeypatch.setattr("sys.argv", ["goldenboy", "plan"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2

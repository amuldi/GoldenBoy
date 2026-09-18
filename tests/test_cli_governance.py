"""End-to-end tests against goldenboy.cli.main() for the new governance
commands: policy, route, audit, spend, snapshot, loop, failure, heartbeat."""
import json
import subprocess

import pytest

from goldenboy.cli import main
from goldenboy.core.router import ModelTier


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["goldenboy"] + argv)
    main()


def _git(repo_dir, *args):
    subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True)


# --- policy --------------------------------------------------------------


def test_policy_allow_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["policy", "bash", "--command", "ls -la"])
    assert "ALLOW" in capsys.readouterr().out


def test_policy_deny_exits_one(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["policy", "bash", "--command", "rm -rf /"])
    assert exc_info.value.code == 1
    assert "DENY" in capsys.readouterr().out


def test_policy_require_approval_exits_two(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["policy", "bash", "--command", "git push origin main"])
    assert exc_info.value.code == 2
    assert "REQUIRE_APPROVAL" in capsys.readouterr().out


def test_policy_command_flag_does_not_clobber_subcommand_dispatch(tmp_path, monkeypatch, capsys):
    """Regression test: --command on the policy subparser must not collide
    with the top-level subparsers' dest='command' used for dispatch."""
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["policy", "bash", "--command", "echo hi", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "allow"


def test_policy_malformed_policy_file_errors_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bad_policy = tmp_path / "bad_policy.json"
    bad_policy.write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["policy", "bash", "--policy-file", str(bad_policy)])
    assert exc_info.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_policy_with_audit_flag_writes_audit_log(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["policy", "bash", "--command", "ls", "--audit"])
    capsys.readouterr()

    from goldenboy.core.audit import AuditStore
    events = AuditStore().load_events().events
    assert len(events) == 1
    assert events[0].action == "policy_check"


# --- route -----------------------------------------------------------------


def test_route_json_output(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["route", "Fix a typo in the README", "--budget", "80", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["tier"] in {t.value for t in ModelTier}


def test_route_text_output(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["route", "Fix a typo in the README", "--budget", "80"])
    out = capsys.readouterr().out
    assert "Golden Boy Model Router" in out
    assert "Routed tier:" in out
    assert "unconfigured" in out


def test_route_malformed_router_file_errors_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bad_router = tmp_path / "bad_router.json"
    bad_router.write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["route", "Fix a typo", "--router-file", str(bad_router)])
    assert exc_info.value.code == 1
    assert "error:" in capsys.readouterr().err


# --- audit -------------------------------------------------------------


def test_audit_empty_says_none_recorded(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["audit"])
    assert "No audit entries" in capsys.readouterr().out


def test_audit_json_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["audit", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"] == []


def test_audit_json_with_entries(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["policy", "bash", "--command", "ls", "--audit"])
    capsys.readouterr()
    _run(monkeypatch, ["audit", "--json", "--limit", "1"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["entries"]) == 1


# --- spend ---------------------------------------------------------------


def test_spend_record_then_status_shows_remaining(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, [
        "spend", "record", "--label", "Task A", "--estimated-tokens", "20000",
        "--actual-tokens", "17000", "--budget-limit", "100000", "--window", "all", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert payload["committed_tokens"] == 17000
    assert payload["remaining_tokens"] == 83000


def test_spend_over_limit_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, [
            "spend", "record", "--label", "Big", "--estimated-tokens", "10",
            "--actual-tokens", "999999", "--budget-limit", "100", "--window", "all",
        ])
    assert exc_info.value.code == 1


def test_spend_record_requires_label_and_estimated_tokens(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["spend", "record"])
    assert exc_info.value.code == 1
    assert "--label" in capsys.readouterr().err


def test_spend_record_rejects_negative_tokens(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["spend", "record", "--label", "x", "--estimated-tokens", "-5"])
    assert exc_info.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_spend_reset_session(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["spend", "reset-session", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "session_start" in payload


def test_spend_status_without_recording(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["spend", "status", "--window", "daily"])
    assert "Spending ledger (daily)" in capsys.readouterr().out


# --- loop ------------------------------------------------------------------


def test_loop_record_stops_at_threshold(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for _ in range(2):
        _run(monkeypatch, ["loop", "record", "--tool", "pytest", "--args", "a", "--error", "b"])
        capsys.readouterr()
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, [
            "loop", "record", "--tool", "pytest", "--args", "a", "--error", "b", "--threshold", "3",
        ])
    assert exc_info.value.code == 1


def test_loop_record_requires_tool(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["loop", "record"])
    assert exc_info.value.code == 1
    assert "--tool" in capsys.readouterr().err


def test_loop_status_empty_then_populated(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["loop", "status"])
    assert "No tracked signatures" in capsys.readouterr().out

    _run(monkeypatch, ["loop", "record", "--tool", "pytest"])
    capsys.readouterr()
    _run(monkeypatch, ["loop", "status", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1


def test_loop_reset(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["loop", "record", "--tool", "pytest"])
    capsys.readouterr()
    _run(monkeypatch, ["loop", "reset", "--json"])
    capsys.readouterr()
    _run(monkeypatch, ["loop", "status"])
    assert "No tracked signatures" in capsys.readouterr().out


# --- failure -----------------------------------------------------------


def test_failure_record_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["failure", "record", "--cause", "connection timeout", "--task-type", "bug_fix"])
    capsys.readouterr()
    _run(monkeypatch, ["failure", "list", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["cause_summary"] == "connection timeout"


def test_failure_list_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["failure", "list"])
    assert "No failure records yet" in capsys.readouterr().out


def test_failure_record_requires_cause(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["failure", "record"])
    assert exc_info.value.code == 1
    assert "--cause" in capsys.readouterr().err


def test_failure_resolve_cycle(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["failure", "record", "--cause", "flaky test", "--json"])
    record = json.loads(capsys.readouterr().out)

    _run(monkeypatch, [
        "failure", "resolve", "--signature", record["signature"], "--resolution", "added a retry", "--json",
    ])
    resolved = json.loads(capsys.readouterr().out)
    assert resolved["resolved"] is True
    assert resolved["resolution"] == "added a retry"


def test_failure_resolve_requires_signature_and_resolution(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["failure", "resolve"])
    assert exc_info.value.code == 1
    assert "--signature" in capsys.readouterr().err


def test_failure_resolve_unknown_signature(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["failure", "resolve", "--signature", "doesnotexist", "--resolution", "n/a"])
    assert exc_info.value.code == 1
    assert "no failure record" in capsys.readouterr().err


def test_failure_similar_requires_cause(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["failure", "similar"])
    assert exc_info.value.code == 1
    assert "--cause" in capsys.readouterr().err


def test_failure_similar_none_found(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["failure", "similar", "--cause", "nothing recorded yet"])
    assert "No similar past failures" in capsys.readouterr().out


def test_failure_similar_json_with_match(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["failure", "record", "--cause", "connection timeout to the API"])
    capsys.readouterr()
    _run(monkeypatch, ["failure", "similar", "--cause", "connection timeout to the API", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["similarity"] == 1.0


# --- snapshot ------------------------------------------------------------


def test_snapshot_create_verify_rollback_cycle(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.py").write_text("print(1)\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "init")

    _run(monkeypatch, ["snapshot", "create", "--label", "before"])
    capsys.readouterr()

    (tmp_path / "a.py").write_text("this is not valid python(\n")

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, [
            "snapshot", "verify", "--check", "python3 -c \"import ast; ast.parse(open('a.py').read())\"",
            "--rollback-on-fail",
        ])
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "Rolled back" in out
    assert (tmp_path / "a.py").read_text() == "print(1)\n"


def test_snapshot_outside_git_repo_errors_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["snapshot", "create"])
    assert exc_info.value.code == 1
    assert "git repository" in capsys.readouterr().err


def _init_git_repo(path):
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "a.py").write_text("print(1)\n")
    _git(path, "add", "a.py")
    _git(path, "commit", "-q", "-m", "init")


def test_snapshot_list_empty_then_populated(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    _run(monkeypatch, ["snapshot", "list"])
    assert "No snapshots recorded yet" in capsys.readouterr().out

    _run(monkeypatch, ["snapshot", "create", "--label", "one", "--json"])
    capsys.readouterr()
    _run(monkeypatch, ["snapshot", "list", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["label"] == "one"


def test_snapshot_verify_passes_without_rollback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    _run(monkeypatch, ["snapshot", "create"])
    capsys.readouterr()

    _run(monkeypatch, ["snapshot", "verify", "--check", "python3 -c \"print('ok')\"", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True


def test_snapshot_verify_requires_at_least_one_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["snapshot", "verify"])
    assert exc_info.value.code == 1
    assert "--check" in capsys.readouterr().err


def test_snapshot_rollback_by_id(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    _run(monkeypatch, ["snapshot", "create", "--label", "first", "--json"])
    first = json.loads(capsys.readouterr().out)

    (tmp_path / "a.py").write_text("print(2)\n")
    _run(monkeypatch, ["snapshot", "create", "--label", "second", "--json"])
    capsys.readouterr()

    (tmp_path / "a.py").write_text("print('broken')\n")
    _run(monkeypatch, ["snapshot", "rollback", "--id", first["id"], "--json"])
    restored = json.loads(capsys.readouterr().out)
    assert restored["id"] == first["id"]
    assert (tmp_path / "a.py").read_text() == "print(1)\n"


def test_snapshot_rollback_unknown_id(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    _run(monkeypatch, ["snapshot", "create"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["snapshot", "rollback", "--id", "doesnotexist"])
    assert exc_info.value.code == 1
    assert "no snapshot with id" in capsys.readouterr().err


def test_snapshot_rollback_with_no_snapshots_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, ["snapshot", "rollback"])
    assert exc_info.value.code == 1
    assert "No snapshot" in capsys.readouterr().err


# --- heartbeat -----------------------------------------------------------


def test_heartbeat_reports_no_wake_when_nothing_changed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["heartbeat", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["should_wake"] is False


def test_heartbeat_wakes_on_exhausted_budget(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, ["heartbeat", "--budget", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["should_wake"] is True

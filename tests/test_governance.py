import json

import pytest

from goldenboy.core.audit import AuditStore
from goldenboy.core.errors import PolicyError
from goldenboy.core.governance import ActionRequest, PolicyConfig, PolicyEngine, PolicyVerdict


def test_allowed_action_returns_allow():
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="bash", command="ls -la", estimated_cost_percentage=5.0))
    assert result.verdict == PolicyVerdict.ALLOW
    assert result.check == "none"


def test_denied_tool_returns_deny():
    config = PolicyConfig(denied_tools=["dangerous_tool"])
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="dangerous_tool"))
    assert result.verdict == PolicyVerdict.DENY
    assert result.check == "permission"
    assert result.reason_code == "TOOL_DENIED"


def test_approval_required_tool_returns_require_approval():
    config = PolicyConfig(approval_required_tools=["deploy"])
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="deploy"))
    assert result.verdict == PolicyVerdict.REQUIRE_APPROVAL
    assert result.reason_code == "TOOL_REQUIRES_APPROVAL"


def test_dangerous_command_returns_deny():
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="bash", command="rm -rf /"))
    assert result.verdict == PolicyVerdict.DENY
    assert result.check == "risk"
    assert result.reason_code == "DANGEROUS_COMMAND"


def test_approval_command_returns_require_approval():
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="bash", command="git push origin main"))
    assert result.verdict == PolicyVerdict.REQUIRE_APPROVAL
    assert result.reason_code == "COMMAND_REQUIRES_APPROVAL"


def test_safe_command_not_flagged():
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="bash", command="ls -la && pytest tests/"))
    assert result.verdict == PolicyVerdict.ALLOW


@pytest.mark.parametrize(
    "path", [".env", "config/.env.local", "secrets/api_secret.txt", "id_rsa", ".ssh/id_ed25519"]
)
def test_protected_path_returns_deny(path):
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="file_write", file_paths=[path]))
    assert result.verdict == PolicyVerdict.DENY
    assert result.check == "scope"
    assert result.reason_code == "PROTECTED_PATH"


def test_ordinary_path_is_allowed():
    engine = PolicyEngine(config=PolicyConfig())
    result = engine.evaluate(ActionRequest(tool="file_write", file_paths=["src/app.py"]))
    assert result.verdict == PolicyVerdict.ALLOW


def test_session_call_limit_denies_when_reached():
    config = PolicyConfig(max_calls_per_session_per_tool=2)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="bash", session_calls_for_tool=2))
    assert result.verdict == PolicyVerdict.DENY
    assert result.reason_code == "SESSION_CALL_LIMIT_EXCEEDED"


def test_session_call_limit_allows_below_threshold():
    config = PolicyConfig(max_calls_per_session_per_tool=2)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="bash", session_calls_for_tool=1))
    assert result.verdict == PolicyVerdict.ALLOW


def test_session_budget_exceeded_denies():
    config = PolicyConfig(session_budget_limit_percentage=50.0)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(
        ActionRequest(tool="bash", estimated_cost_percentage=10.0, session_spent_percentage=45.0)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert result.reason_code == "SESSION_BUDGET_EXCEEDED"


def test_daily_budget_exceeded_denies():
    config = PolicyConfig(day_budget_limit_percentage=80.0)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(
        ActionRequest(tool="bash", estimated_cost_percentage=10.0, day_spent_percentage=75.0)
    )
    assert result.verdict == PolicyVerdict.DENY
    assert result.reason_code == "DAILY_BUDGET_EXCEEDED"


def test_single_action_cost_above_threshold_requires_approval_not_deny():
    config = PolicyConfig(max_single_action_cost_percentage=10.0)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="bash", estimated_cost_percentage=15.0))
    assert result.verdict == PolicyVerdict.REQUIRE_APPROVAL
    assert result.reason_code == "SINGLE_ACTION_COST_ABOVE_THRESHOLD"


def test_check_order_permission_before_budget():
    """A denied tool is caught by the permission check even if it would
    also fail the budget check -- the first failing check wins, and it
    should be the earliest one in the pipeline."""
    config = PolicyConfig(denied_tools=["bash"], max_calls_per_session_per_tool=1)
    engine = PolicyEngine(config=config)
    result = engine.evaluate(ActionRequest(tool="bash", session_calls_for_tool=5))
    assert result.check == "permission"


def test_evaluate_writes_to_audit_store_when_provided(tmp_path):
    store = AuditStore(history_dir=str(tmp_path))
    engine = PolicyEngine(config=PolicyConfig(), audit_store=store)
    engine.evaluate(ActionRequest(tool="bash", command="rm -rf /"), task_id="task-1")

    result = store.load_events()
    assert len(result.events) == 1
    entry = result.events[0]
    assert entry.action == "policy_check"
    assert entry.result == "blocked"
    assert entry.decision == "deny"
    assert entry.task_id == "task-1"


def test_no_audit_store_means_no_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = PolicyEngine(config=PolicyConfig())
    engine.evaluate(ActionRequest(tool="bash"))
    assert not (tmp_path / ".goldenboy" / "audit.jsonl").exists()


# --- PolicyConfig ------------------------------------------------------


def test_policy_config_defaults_when_file_missing(tmp_path):
    config = PolicyConfig.load(str(tmp_path / "does_not_exist.json"))
    assert config == PolicyConfig()


def test_policy_config_json_file_replaces_default_lists(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"denied_tools": ["only_this_one"]}))
    config = PolicyConfig.load(str(path))
    assert config.denied_tools == ["only_this_one"]
    # Defaults for other list fields are untouched.
    assert config.denied_command_patterns == PolicyConfig().denied_command_patterns


def test_policy_config_malformed_json_raises_policyerror(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("{not valid json")
    with pytest.raises(PolicyError, match="Could not parse"):
        PolicyConfig.load(str(path))


def test_policy_config_unknown_key_raises_policyerror(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"totally_made_up_key": 1}))
    with pytest.raises(PolicyError, match="unknown key"):
        PolicyConfig.load(str(path))


def test_policy_config_invalid_regex_raises_policyerror():
    with pytest.raises(PolicyError):
        PolicyConfig(denied_command_patterns=["("])


def test_policy_config_env_var_overrides_numeric_field(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLDENBOY_POLICY_MAX_SINGLE_ACTION_COST_PERCENTAGE", "12.5")
    config = PolicyConfig.load(str(tmp_path / "does_not_exist.json"))
    assert config.max_single_action_cost_percentage == 12.5

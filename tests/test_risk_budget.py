import pytest

from goldenboy.core.governance import PolicyVerdict
from goldenboy.core.risk_budget import RiskBudgetConfig, RiskBudgetEngine, RiskBudgetError


def test_first_low_weight_operation_allows(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    result = engine.record("read_file")
    assert result.verdict == PolicyVerdict.ALLOW
    assert result.remaining == pytest.approx(99.0)


def test_unknown_operation_uses_unknown_weight(tmp_path):
    config = RiskBudgetConfig(unknown_operation_weight=7.0)
    engine = RiskBudgetEngine(config=config, state_dir=str(tmp_path))
    result = engine.record("some_never_seen_operation")
    assert result.weight_applied == 7.0
    assert result.remaining == pytest.approx(93.0)


def test_cumulative_deduction_across_calls(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    engine.record("shell_command")  # -8
    result = engine.record("modify_source")  # -3
    assert result.remaining == pytest.approx(100.0 - 8.0 - 3.0)


def test_crosses_approval_threshold(tmp_path):
    config = RiskBudgetConfig(initial_budget=50.0, approval_threshold=40.0, deny_threshold=10.0)
    engine = RiskBudgetEngine(config=config, state_dir=str(tmp_path))
    result = engine.record("dependency_change")  # -10 -> remaining 40, at threshold
    assert result.verdict == PolicyVerdict.REQUIRE_APPROVAL


def test_crosses_deny_threshold(tmp_path):
    config = RiskBudgetConfig(initial_budget=50.0, approval_threshold=40.0, deny_threshold=10.0)
    engine = RiskBudgetEngine(config=config, state_dir=str(tmp_path))
    engine.record("dangerous_operation")  # -40 -> remaining 10
    result = engine.record("read_file")  # -1 -> remaining 9
    assert result.verdict == PolicyVerdict.DENY


def test_remaining_never_goes_below_zero(tmp_path):
    config = RiskBudgetConfig(initial_budget=10.0, approval_threshold=5.0, deny_threshold=1.0)
    engine = RiskBudgetEngine(config=config, state_dir=str(tmp_path))
    engine.record("dangerous_operation")  # -40, floored at 0
    result = engine.record("read_file")
    assert result.remaining == 0.0
    assert result.verdict == PolicyVerdict.DENY


def test_repeat_count_adds_penalty_beyond_first(tmp_path):
    config = RiskBudgetConfig(repeat_failure_penalty=5.0)
    engine = RiskBudgetEngine(config=config, state_dir=str(tmp_path))
    result = engine.record("shell_command", repeat_count=3)
    # base 8.0 + 2 extra repeats * 5.0 penalty = 18.0
    assert result.weight_applied == pytest.approx(18.0)


def test_repeat_count_of_one_applies_no_penalty(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    result = engine.record("shell_command", repeat_count=1)
    assert result.weight_applied == pytest.approx(8.0)


def test_repeat_count_below_one_raises(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    with pytest.raises(ValueError):
        engine.record("read_file", repeat_count=0)


def test_state_persists_across_instances(tmp_path):
    RiskBudgetEngine(state_dir=str(tmp_path)).record("modify_source")
    engine2 = RiskBudgetEngine(state_dir=str(tmp_path))
    result = engine2.record("modify_source")
    assert result.remaining == pytest.approx(100.0 - 3.0 - 3.0)


def test_reset_restores_initial_budget(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    engine.record("dangerous_operation")
    engine.reset()
    status = engine.status()
    assert status.remaining == 100.0
    assert status.operations_recorded == 0


def test_status_reports_totals_without_recording(tmp_path):
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    engine.record("read_file")
    engine.record("modify_source")
    status = engine.status()
    assert status.operations_recorded == 2
    assert status.total_deducted == pytest.approx(4.0)


def test_config_rejects_invalid_threshold_ordering():
    with pytest.raises(RiskBudgetError):
        RiskBudgetConfig(approval_threshold=5.0, deny_threshold=10.0)


def test_config_rejects_negative_operation_weight():
    with pytest.raises(RiskBudgetError):
        RiskBudgetConfig(operation_weights={"bad": -1.0})


def test_config_load_from_json_file(tmp_path):
    config_path = tmp_path / "risk_budget.json"
    config_path.write_text('{"initial_budget": 200.0, "deny_threshold": 20.0, "approval_threshold": 60.0}')
    config = RiskBudgetConfig.load(str(config_path))
    assert config.initial_budget == 200.0
    assert config.deny_threshold == 20.0


def test_config_load_rejects_unknown_key(tmp_path):
    config_path = tmp_path / "risk_budget.json"
    config_path.write_text('{"not_a_real_field": 1}')
    with pytest.raises(RiskBudgetError):
        RiskBudgetConfig.load(str(config_path))


def test_config_load_missing_file_uses_defaults(tmp_path):
    config = RiskBudgetConfig.load(str(tmp_path / "does_not_exist.json"))
    assert config.initial_budget == 100.0


def test_corrupted_state_file_raises(tmp_path):
    state_file = tmp_path / "risk_budget_state.json"
    state_file.write_text("not valid json")
    engine = RiskBudgetEngine(state_dir=str(tmp_path))
    with pytest.raises(RiskBudgetError):
        engine.status()


def test_config_and_state_files_do_not_collide(tmp_path):
    """Regression test: the default config path (.goldenboy/risk_budget.json)
    and the default state path must not be the same file -- recording once
    must not corrupt a subsequent RiskBudgetConfig.load() from the same
    directory."""
    config_path = tmp_path / "risk_budget.json"
    config_path.write_text('{"initial_budget": 100.0}')

    engine = RiskBudgetEngine(config=RiskBudgetConfig.load(str(config_path)), state_dir=str(tmp_path))
    engine.record("shell_command")

    # Loading config from the same directory afterward must still work --
    # it must not have been overwritten by the engine's own state write.
    reloaded_config = RiskBudgetConfig.load(str(config_path))
    assert reloaded_config.initial_budget == 100.0

import pytest

from goldenboy.core.telemetry import (
    ExecutionTelemetry,
    TelemetryError,
    TelemetryStore,
)


def test_create_requires_only_final_outcome():
    event = ExecutionTelemetry.create(final_outcome="completed")
    assert event.final_outcome == "completed"
    assert event.verification_status is None
    assert event.actual_cost_percentage is None


def test_create_rejects_invalid_final_outcome():
    with pytest.raises(ValueError):
        ExecutionTelemetry.create(final_outcome="not_a_real_outcome")


def test_create_rejects_invalid_verification_status():
    with pytest.raises(ValueError):
        ExecutionTelemetry.create(final_outcome="completed", verification_status="TOTALLY_SURE")


def test_actual_cost_percentage_is_derived_from_tokens_and_budget():
    event = ExecutionTelemetry.create(
        final_outcome="completed",
        actual_total_tokens=25_000,
        max_budget_tokens=100_000,
    )
    assert event.actual_cost_percentage == 25.0


def test_actual_cost_percentage_is_none_without_actual_tokens():
    event = ExecutionTelemetry.create(final_outcome="completed")
    assert event.actual_cost_percentage is None


def test_round_trip_through_dict():
    event = ExecutionTelemetry.create(
        final_outcome="failed",
        verification_status="FAILED",
        failure_reason="test suite regressed",
        task_id="abc123",
        actual_total_tokens=5000,
        tests_run=10,
        tests_passed=7,
        tests_failed=3,
    )
    restored = ExecutionTelemetry.from_dict(event.to_dict())
    assert restored == event


def test_from_dict_tolerates_unknown_future_fields():
    """A payload from a future schema version with extra top-level keys
    should not raise -- unknown keys are dropped, not rejected."""
    data = ExecutionTelemetry.create(final_outcome="completed").to_dict()
    data["some_future_field"] = "unexpected"
    restored = ExecutionTelemetry.from_dict(data)
    assert restored.final_outcome == "completed"


def test_from_dict_raises_on_missing_required_field():
    with pytest.raises(ValueError):
        ExecutionTelemetry.from_dict({"schema_version": 1, "recorded_at": "now"})


def test_store_append_and_load_round_trip(tmp_path):
    store = TelemetryStore(history_dir=str(tmp_path))
    event = ExecutionTelemetry.create(final_outcome="completed", actual_total_tokens=1000)
    store.append(event)

    result = store.load_events()
    assert result.total_lines == 1
    assert result.corrupted_lines == 0
    assert result.events == [event]


def test_store_load_on_missing_file_returns_empty_result(tmp_path):
    store = TelemetryStore(history_dir=str(tmp_path / "does_not_exist"))
    result = store.load_events()
    assert result.events == []
    assert result.total_lines == 0


def test_store_load_tolerates_one_corrupted_line(tmp_path):
    store = TelemetryStore(history_dir=str(tmp_path))
    store.append(ExecutionTelemetry.create(final_outcome="completed"))
    with open(store.telemetry_file, "a", encoding="utf-8") as f:
        f.write("not valid json\n")
    store.append(ExecutionTelemetry.create(final_outcome="failed"))

    result = store.load_events()
    assert len(result.events) == 2
    assert result.corrupted_lines == 1
    assert result.total_lines == 3


def test_store_clear_removes_file(tmp_path):
    store = TelemetryStore(history_dir=str(tmp_path))
    store.append(ExecutionTelemetry.create(final_outcome="completed"))
    store.clear()
    assert store.load_events().events == []


def test_write_failure_raises_telemetry_error(tmp_path, monkeypatch):
    store = TelemetryStore(history_dir=str(tmp_path / "readonly"))

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _boom)
    with pytest.raises(TelemetryError):
        store.append(ExecutionTelemetry.create(final_outcome="completed"))

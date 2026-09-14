import json
import os

import pytest

from goldenboy.core.history import HISTORY_SCHEMA_VERSION, HistoryError, HistoryStore, TaskEvent


def _event(**overrides):
    defaults = dict(
        task_text="Fix a bug in the login flow",
        task_type="bug_fix",
        task_type_confidence=0.8,
        priority="P1",
        estimated_cost_percentage=12.0,
        estimated_cost_confidence=0.85,
        usage_source="mock",
        usage_confidence="EXACT",
        remaining_usage_start=40.0,
        decision_mode="SAFE",
        outcome="completed",
    )
    defaults.update(overrides)
    return TaskEvent.create(**defaults)


def test_event_never_stores_raw_task_text():
    event = _event(task_text="super secret proprietary prompt text")
    data = event.to_dict()
    assert "super secret proprietary prompt text" not in json.dumps(data)
    assert data["prompt_length"] == len("super secret proprietary prompt text")
    assert len(data["prompt_hash"]) == 16


def test_append_and_load_round_trip(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    event = _event()
    store.append(event)

    result = store.load_events()
    assert result.total_lines == 1
    assert result.corrupted_lines == 0
    assert len(result.events) == 1
    assert result.events[0].task_type == "bug_fix"
    assert result.events[0].schema_version == HISTORY_SCHEMA_VERSION


def test_load_events_on_missing_file_is_empty_not_an_error(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    result = store.load_events()
    assert result.events == []
    assert result.total_lines == 0
    assert result.corrupted_lines == 0


def test_corrupted_line_is_skipped_not_fatal(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    history_file = history_dir / "history.jsonl"

    store = HistoryStore(history_dir=str(history_dir))
    store.append(_event())
    with open(history_file, "a", encoding="utf-8") as f:
        f.write("{not valid json\n")
    store.append(_event(outcome="deferred"))

    result = store.load_events()
    assert result.total_lines == 3
    assert result.corrupted_lines == 1
    assert len(result.events) == 2


def test_missing_required_field_counts_as_corrupted(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    history_file = history_dir / "history.jsonl"
    with open(history_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema_version": 1}) + "\n")

    store = HistoryStore(history_dir=str(history_dir))
    result = store.load_events()
    assert result.corrupted_lines == 1
    assert result.events == []


def test_clear_removes_the_file(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event())
    assert os.path.exists(store.history_file)

    store.clear()
    assert not os.path.exists(store.history_file)


def test_append_multiple_events_preserves_order(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event(outcome="completed"))
    store.append(_event(outcome="deferred"))
    store.append(_event(outcome="failed"))

    result = store.load_events()
    assert [e.outcome for e in result.events] == ["completed", "deferred", "failed"]


def test_write_failure_raises_history_error(tmp_path, monkeypatch):
    store = HistoryStore(history_dir=str(tmp_path / "readonly"))

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _boom)
    with pytest.raises(HistoryError):
        store.append(_event())

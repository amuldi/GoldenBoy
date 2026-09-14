import json

from goldenboy.analytics.data_quality import validate
from goldenboy.core.history import HistoryStore, TaskEvent


def _event(**overrides):
    defaults = dict(
        task_text="Fix a bug",
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


def test_empty_history_is_no_data(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    report = validate(store)

    assert report.total_lines == 0
    assert report.status == "NO_DATA"
    assert "insufficient" in report.render().lower()


def test_all_valid_events_is_good(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    for _ in range(20):
        store.append(_event())

    report = validate(store)
    assert report.status == "GOOD"
    assert report.corrupted_rows == 0
    assert report.invalid_value_rows == 0
    assert report.valid_rows == 20


def test_corrupted_lines_are_counted(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    store = HistoryStore(history_dir=str(history_dir))
    store.append(_event())
    with open(store.history_file, "a", encoding="utf-8") as f:
        f.write("{not valid json\n")

    report = validate(store)
    assert report.corrupted_rows == 1
    assert report.total_lines == 2


def test_out_of_range_percentage_is_an_invalid_value_row(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    store = HistoryStore(history_dir=str(history_dir))
    event = _event(estimated_cost_percentage=150.0)
    with open(store.history_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict()) + "\n")

    report = validate(store)
    assert report.invalid_value_rows == 1
    assert "estimated_cost_percentage" in report.issues


def test_duplicate_events_are_detected(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    store = HistoryStore(history_dir=str(history_dir))
    event = _event()
    with open(store.history_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict()) + "\n")
        f.write(json.dumps(event.to_dict()) + "\n")  # exact duplicate line

    report = validate(store)
    assert report.duplicate_rows == 1


def test_status_degrades_with_high_invalid_ratio(tmp_path):
    history_dir = tmp_path / ".goldenboy"
    history_dir.mkdir()
    store = HistoryStore(history_dir=str(history_dir))
    # 10 good events, 1 corrupted -> ~9% invalid ratio -> POOR (> 5%)
    for _ in range(10):
        store.append(_event())
    with open(store.history_file, "a", encoding="utf-8") as f:
        f.write("{not valid json\n")

    report = validate(store)
    assert report.status == "POOR"


def test_render_includes_status_line(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event())
    report = validate(store)
    assert "Status:" in report.render()

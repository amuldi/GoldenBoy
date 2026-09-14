from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore, TaskEvent


def _event(**overrides):
    defaults = dict(
        task_text="Fix a bug",
        task_type="bug_fix",
        task_type_confidence=0.8,
        priority="P1",
        estimated_cost_percentage=10.0,
        estimated_cost_confidence=0.85,
        usage_source="mock",
        usage_confidence="EXACT",
        remaining_usage_start=40.0,
        decision_mode="SAFE",
        outcome="completed",
        duration_seconds=1.0,
    )
    defaults.update(overrides)
    return TaskEvent.create(**defaults)


def test_empty_history_reports_none_everywhere(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    report = analyze(store)

    assert report.event_count == 0
    assert report.mean_cost_percentage is None
    assert report.completion_rate is None
    assert "insufficient" in report.render().lower()


def test_completion_failure_deferral_rates(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event(outcome="completed"))
    store.append(_event(outcome="completed"))
    store.append(_event(outcome="failed"))
    store.append(_event(outcome="deferred"))

    report = analyze(store)

    assert report.event_count == 4
    assert report.completion_rate == 0.5
    assert report.failure_rate == 0.25
    assert report.deferral_rate == 0.25


def test_mean_cost_by_task_type(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event(task_type="bug_fix", estimated_cost_percentage=10.0))
    store.append(_event(task_type="bug_fix", estimated_cost_percentage=20.0))
    store.append(_event(task_type="refactor", estimated_cost_percentage=40.0))

    report = analyze(store)

    assert report.mean_cost_by_task_type["bug_fix"] == 15.0
    assert report.mean_cost_by_task_type["refactor"] == 40.0


def test_mode_distribution_is_counted(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event(decision_mode="SAFE"))
    store.append(_event(decision_mode="SAFE"))
    store.append(_event(decision_mode="CRITICAL"))

    report = analyze(store)

    assert report.mode_distribution == {"SAFE": 2, "CRITICAL": 1}


def test_render_does_not_crash_with_data(tmp_path):
    store = HistoryStore(history_dir=str(tmp_path / ".goldenboy"))
    store.append(_event())
    report = analyze(store)
    text = report.render()
    assert "Completion rate" in text

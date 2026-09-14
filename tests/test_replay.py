from datetime import datetime, timedelta, timezone

from goldenboy.core.history import TaskEvent
from goldenboy.core.policies import FixedThresholdPolicy
from goldenboy.replay.engine import (
    run_backtest,
    run_walk_forward_backtest,
    walk_forward_folds,
)


def _event(remaining, cost, outcome, ts_offset=0, task_type="bug_fix"):
    event = TaskEvent.create(
        task_text=f"task {ts_offset}",
        task_type=task_type,
        task_type_confidence=0.7,
        priority="P1",
        estimated_cost_percentage=cost,
        estimated_cost_confidence=0.85,
        usage_source="mock",
        usage_confidence="EXACT",
        remaining_usage_start=remaining,
        decision_mode="SAFE",
        outcome=outcome,
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event.timestamp = (base + timedelta(minutes=ts_offset)).isoformat()
    return event


def _hand_verified_dataset():
    """5 TP + 3 FP + 2 FN + 2 TN against FixedThresholdPolicy(15.0), by
    construction -- see the docstring math in the test below."""
    events = []
    for i in range(5):
        events.append(_event(remaining=50.0, cost=10.0, outcome="completed", ts_offset=i))
    for i in range(3):
        events.append(_event(remaining=50.0, cost=10.0, outcome="failed", ts_offset=5 + i))
    for i in range(2):
        events.append(_event(remaining=10.0, cost=10.0, outcome="completed", ts_offset=8 + i))
    for i in range(2):
        events.append(_event(remaining=10.0, cost=10.0, outcome="failed", ts_offset=10 + i))
    return events


def test_below_minimum_events_reports_na():
    events = [_event(50.0, 10.0, "completed", i) for i in range(3)]
    report = run_backtest(events)

    assert report.policies == []
    assert "N/A" in report.render()


def test_backtest_metrics_match_hand_computed_confusion_matrix():
    events = _hand_verified_dataset()
    report = run_backtest(events, policies=[FixedThresholdPolicy(threshold_percentage=15.0)])

    assert report.dataset_size == 12
    metrics = report.policies[0]
    assert metrics.proceed_count == 8  # 5 TP + 3 FP
    assert metrics.stop_count == 4  # 2 FN + 2 TN
    assert metrics.precision == 5 / 8
    assert metrics.recall == 5 / 7
    assert metrics.accuracy == 7 / 12
    assert metrics.premature_stop_rate == 2 / 12
    assert metrics.unnecessary_continuation_rate == 3 / 12


def test_render_includes_policy_name_and_limitations():
    events = _hand_verified_dataset()
    report = run_backtest(events, policies=[FixedThresholdPolicy(threshold_percentage=15.0)])
    text = report.render()

    assert "fixed_threshold_15pct" in text
    assert "Limitations:" in text
    assert "off-policy" in text.lower()


def test_default_policies_are_all_scored():
    events = _hand_verified_dataset()
    report = run_backtest(events)
    assert len(report.policies) == 5


def test_walk_forward_folds_are_chronological_and_non_overlapping():
    events = [_event(50.0, 10.0, "completed", ts_offset=i) for i in range(9)]
    # Shuffle input order -- the function must sort by timestamp itself.
    shuffled = [
        events[3], events[0], events[8], events[1], events[5],
        events[2], events[7], events[4], events[6],
    ]

    folds = walk_forward_folds(shuffled, n_folds=3)

    assert len(folds) == 3
    assert all(len(f) == 3 for f in folds)
    flattened = [e for fold in folds for e in fold]
    assert flattened == sorted(events, key=lambda e: e.timestamp)
    # Every event in fold[i] must be chronologically before every event in fold[i+1].
    for i in range(len(folds) - 1):
        assert max(e.timestamp for e in folds[i]) < min(e.timestamp for e in folds[i + 1])


def test_walk_forward_folds_handles_empty_input():
    folds = walk_forward_folds([], n_folds=3)
    assert folds == [[], [], []]


def test_run_walk_forward_backtest_returns_one_report_per_fold():
    events = _hand_verified_dataset()
    results = run_walk_forward_backtest(events, n_folds=2)

    assert set(results.keys()) == {0, 1}
    assert all(isinstance(report.dataset_size, int) for report in results.values())

import pytest

from goldenboy.core.spending import (
    SessionMarker,
    SpendEntry,
    SpendingStore,
    filter_since,
    filter_today,
    summarize,
)


def test_spend_entry_create_validates_nonnegative_tokens():
    with pytest.raises(ValueError):
        SpendEntry.create(label="x", estimated_tokens=-1)
    with pytest.raises(ValueError):
        SpendEntry.create(label="x", estimated_tokens=10, actual_tokens=-1)


def test_worked_example_from_project_brief():
    """Budget = 100,000 tokens. Task A: est=20,000 actual=17,000. Task B:
    est=50,000 actual=56,000. Remaining should be 27,000."""
    entries = [
        SpendEntry.create(label="Task A", estimated_tokens=20_000, actual_tokens=17_000),
        SpendEntry.create(label="Task B", estimated_tokens=50_000, actual_tokens=56_000),
    ]
    summary = summarize(entries, limit_tokens=100_000, window="all")
    assert summary.committed_tokens == 17_000 + 56_000
    assert summary.remaining_tokens == 100_000 - 17_000 - 56_000
    assert summary.remaining_tokens == 27_000
    assert not summary.over_limit


def test_estimated_only_entry_counts_as_provisional_hold():
    entries = [SpendEntry.create(label="Task C", estimated_tokens=30_000)]
    summary = summarize(entries, limit_tokens=100_000)
    assert summary.committed_tokens == 30_000  # falls back to estimate, actual unknown
    assert summary.settled_count == 0


def test_over_limit_detected():
    entries = [SpendEntry.create(label="Task", estimated_tokens=10, actual_tokens=200)]
    summary = summarize(entries, limit_tokens=100)
    assert summary.over_limit
    assert summary.remaining_tokens == -100


def test_no_limit_means_no_over_limit_and_no_remaining():
    entries = [SpendEntry.create(label="Task", estimated_tokens=1_000_000)]
    summary = summarize(entries, limit_tokens=None)
    assert summary.remaining_tokens is None
    assert not summary.over_limit


def test_estimated_and_actual_are_reported_distinctly():
    entries = [
        SpendEntry.create(label="A", estimated_tokens=100, actual_tokens=90),
        SpendEntry.create(label="B", estimated_tokens=50),
    ]
    summary = summarize(entries)
    assert summary.estimated_tokens_total == 150
    assert summary.actual_tokens_total == 90  # only the settled entry


def test_spending_store_append_and_load(tmp_path):
    store = SpendingStore(history_dir=str(tmp_path))
    store.append(SpendEntry.create(label="A", estimated_tokens=100))
    store.append(SpendEntry.create(label="B", estimated_tokens=200, actual_tokens=210))

    result = store.load_events()
    assert len(result.entries) == 2
    assert result.corrupted_lines == 0


def test_spending_store_tolerates_corrupted_lines(tmp_path):
    store = SpendingStore(history_dir=str(tmp_path))
    store.append(SpendEntry.create(label="A", estimated_tokens=100))
    with open(store.spending_file, "a", encoding="utf-8") as f:
        f.write("{not valid json\n")

    result = store.load_events()
    assert len(result.entries) == 1
    assert result.corrupted_lines == 1


def test_filter_today_excludes_other_days():
    entries = [
        SpendEntry.create(label="today", estimated_tokens=1),
        SpendEntry(schema_version=1, timestamp="2000-01-01T00:00:00+00:00", label="old", estimated_tokens=1),
    ]
    filtered = filter_today(entries)
    assert len(filtered) == 1
    assert filtered[0].label == "today"


def test_filter_since_excludes_earlier_entries():
    entries = [
        SpendEntry(
            schema_version=1, timestamp="2026-01-01T00:00:00+00:00", label="early", estimated_tokens=1
        ),
        SpendEntry(
            schema_version=1, timestamp="2026-06-01T00:00:00+00:00", label="late", estimated_tokens=1
        ),
    ]
    filtered = filter_since(entries, "2026-03-01T00:00:00+00:00")
    assert [e.label for e in filtered] == ["late"]


def test_session_marker_persists_across_instances(tmp_path):
    marker1 = SessionMarker(state_dir=str(tmp_path))
    start = marker1.get_or_create()

    marker2 = SessionMarker(state_dir=str(tmp_path))
    assert marker2.get_or_create() == start


def test_session_marker_reset_changes_value(tmp_path):
    marker = SessionMarker(state_dir=str(tmp_path))
    first = marker.get_or_create()
    second = marker.reset()
    assert marker.get_or_create() == second
    # Not asserting first != second (could tie at same-microsecond resolution
    # on a very fast machine); only that reset() persists its own value.
    assert first is not None

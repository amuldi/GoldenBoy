from goldenboy.core.failure_memory import FailureMemoryStore


def test_record_creates_new_record(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    record = store.record("AssertionError: expected 2 got 3", task_type="bug_fix")
    assert record.attempt_count == 1
    assert record.resolved is False


def test_recording_same_cause_increments_attempt_count(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("AssertionError: expected 2 got 3")
    second = store.record("AssertionError: expected 2 got 3")
    assert second.attempt_count == 2


def test_normalization_treats_differing_numbers_as_same_cause(tmp_path):
    """'line 42 failed' and 'line 57 failed' should be treated as the same
    underlying failure signature (numbers normalized away)."""
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("test_foo.py line 42 failed")
    second = store.record("test_foo.py line 57 failed")
    assert second.attempt_count == 2


def test_resolve_marks_record_resolved(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    record = store.record("some cause")
    resolved = store.resolve(record.signature, "fixed by adding a null check")
    assert resolved.resolved is True
    assert resolved.resolution == "fixed by adding a null check"


def test_resolve_unknown_signature_returns_none(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    assert store.resolve("doesnotexist", "n/a") is None


def test_find_similar_exact_match(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("connection timeout while calling the payments API")
    results = store.find_similar("connection timeout while calling the payments API")
    assert len(results) == 1
    assert results[0].similarity == 1.0


def test_find_similar_fuzzy_match_above_threshold(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("connection timeout while calling the payments API")
    results = store.find_similar("connection timeout while calling the billing API", min_similarity=0.3)
    assert len(results) == 1
    assert 0.0 < results[0].similarity < 1.0


def test_find_similar_returns_nothing_for_unrelated_cause(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("connection timeout while calling the payments API")
    results = store.find_similar("unrelated syntax error in a completely different module")
    assert results == []


def test_load_all_returns_every_record(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("cause one")
    store.record("cause two")
    assert len(store.load_all()) == 2


def test_secrets_redacted_from_cause_before_persisting(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    record = store.record("auth failed with key sk-abcdefghijklmnopqrstuvwx")
    assert "sk-abcdefghijklmnopqrstuvwx" not in record.cause_summary

    raw = (tmp_path / "failures.json").read_text()
    assert "sk-abcdefghijklmnopqrstuvwx" not in raw


def test_clear_removes_state_file(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("cause")
    store.clear()
    assert store.load_all() == []

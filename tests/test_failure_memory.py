import pytest

from goldenboy.core.failure_memory import FailureCategory, FailureMemoryStore, classify_failure


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


# --- Failure classification -----------------------------------------------


@pytest.mark.parametrize(
    "cause,expected",
    [
        ("SyntaxError: invalid syntax on line 12", FailureCategory.SYNTAX),
        ("AssertionError: expected 2 got 3, 1 failed, 4 passed", FailureCategory.TEST_FAILURE),
        ("ModuleNotFoundError: No module named 'requests'", FailureCategory.DEPENDENCY),
        ("PermissionError: Permission denied: '/etc/shadow'", FailureCategory.PERMISSION),
        ("bash: foo: command not found", FailureCategory.ENVIRONMENT),
        ("the operation timed out after 30s", FailureCategory.TIMEOUT),
        ("429 Too Many Requests: rate limit exceeded", FailureCategory.RESOURCE_LIMIT),
        ("request denied by policy: DANGEROUS_COMMAND", FailureCategory.POLICY_DENIAL),
        ("the widget turned an unexpected shade of blue", FailureCategory.UNKNOWN),
    ],
)
def test_classify_failure(cause, expected):
    assert classify_failure(cause) == expected


def test_record_auto_classifies_category(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    record = store.record("ModuleNotFoundError: No module named 'foo'")
    assert record.category == FailureCategory.DEPENDENCY.value


def test_record_explicit_category_overrides_classifier(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    record = store.record("some ambiguous cause", category=FailureCategory.ENVIRONMENT)
    assert record.category == FailureCategory.ENVIRONMENT.value


def test_repeat_record_keeps_original_category(tmp_path):
    store = FailureMemoryStore(state_dir=str(tmp_path))
    store.record("ModuleNotFoundError: No module named 'foo'", category=FailureCategory.ENVIRONMENT)
    second = store.record("ModuleNotFoundError: No module named 'foo'")
    assert second.category == FailureCategory.ENVIRONMENT.value


def test_loading_record_without_category_field_defaults_to_unknown(tmp_path):
    """Backward compatibility: a failures.json written before `category`
    existed must still load cleanly."""
    import json

    state_file = tmp_path / "failures.json"
    state_file.write_text(json.dumps({
        "schema_version": 1,
        "records": {
            "abc123": {
                "schema_version": 1, "signature": "abc123", "cause_summary": "old record",
                "task_type": None, "attempt_count": 1, "first_seen": "t", "last_seen": "t",
            }
        },
    }))
    store = FailureMemoryStore(state_dir=str(tmp_path))
    records = store.load_all()
    assert records[0].category == FailureCategory.UNKNOWN.value

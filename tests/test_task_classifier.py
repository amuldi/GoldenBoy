from goldenboy.core.task_classifier import TaskClassifier
from goldenboy.core.task_types import TaskType


def test_empty_task_is_unknown_with_zero_confidence():
    result = TaskClassifier().classify("")
    assert result.task_type == TaskType.UNKNOWN
    assert result.confidence == 0.0


def test_whitespace_only_task_is_unknown():
    result = TaskClassifier().classify("   \n  ")
    assert result.task_type == TaskType.UNKNOWN


def test_no_keyword_match_is_unknown():
    result = TaskClassifier().classify("zzz qqq xyzzy plugh")
    assert result.task_type == TaskType.UNKNOWN
    assert result.confidence == 0.0


def test_bug_fix_phrasing_is_classified_as_bug_fix():
    result = TaskClassifier().classify("Fix a bug where login crashes on empty password")
    assert result.task_type == TaskType.BUG_FIX
    assert result.confidence > 0.0


def test_refactor_phrasing_is_classified_as_refactor():
    result = TaskClassifier().classify("Refactor the payment module to simplify the retry logic")
    assert result.task_type == TaskType.REFACTOR


def test_testing_phrasing_is_classified_as_testing():
    result = TaskClassifier().classify("Add unit tests and integration tests for the checkout flow")
    assert result.task_type == TaskType.TESTING


def test_documentation_phrasing_is_classified_as_documentation():
    result = TaskClassifier().classify("Update the README and write docs for the new CLI command")
    assert result.task_type == TaskType.DOCUMENTATION


def test_architecture_change_phrasing_is_classified_correctly():
    result = TaskClassifier().classify(
        "Redesign the authentication system architecture to support SSO"
    )
    assert result.task_type == TaskType.ARCHITECTURE_CHANGE


def test_dependency_change_phrasing_is_classified_correctly():
    result = TaskClassifier().classify("Upgrade dependencies to patch a CVE in a vulnerable dependency")
    assert result.task_type == TaskType.DEPENDENCY_CHANGE


def test_release_phrasing_is_classified_correctly():
    result = TaskClassifier().classify("Cut a release and publish the new version")
    assert result.task_type == TaskType.RELEASE


def test_performance_phrasing_is_classified_correctly():
    result = TaskClassifier().classify("Optimize the query to reduce latency and speed up page loads")
    assert result.task_type == TaskType.PERFORMANCE_OPTIMIZATION


def test_confidence_is_bounded_between_zero_and_one():
    for text in [
        "Fix a bug",
        "Refactor and fix a bug and add tests and write documentation for the release",
        "Implement a brand new feature end to end with tests and docs and a release",
    ]:
        result = TaskClassifier().classify(text)
        assert 0.0 <= result.confidence <= 1.0


def test_signals_record_which_phrases_matched():
    result = TaskClassifier().classify("Fix a bug in the parser")
    assert any("bug_fix" in key for key in result.signals)


def test_classification_is_deterministic():
    text = "Refactor the estimator and add tests"
    first = TaskClassifier().classify(text)
    second = TaskClassifier().classify(text)
    assert first.task_type == second.task_type
    assert first.confidence == second.confidence

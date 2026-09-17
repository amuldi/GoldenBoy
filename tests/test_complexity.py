from goldenboy.core.complexity import estimate_task_complexity


def test_empty_task_scores_zero_with_no_signals():
    result = estimate_task_complexity("")
    assert result.score == 0.0
    assert result.signals == []


def test_small_localized_task_scores_low_with_no_signals():
    result = estimate_task_complexity("Fix a typo in the login error message")
    assert result.score == 0.0
    assert result.signals == []


def test_architecture_change_is_detected_and_scored_high():
    result = estimate_task_complexity(
        "Re-architect the data model and migrate the storage layer to the new schema"
    )
    assert "architecture_keyword" in result.signals
    assert "migration_keyword" in result.signals
    assert result.score >= 0.5


def test_cross_module_and_test_signals_are_both_detected():
    result = estimate_task_complexity(
        "Implement OAuth authentication with refresh tokens across the API, "
        "middleware, and client SDK, with full test coverage"
    )
    assert "cross_module_keyword" in result.signals
    assert "test_requirement_keyword" in result.signals


def test_multi_step_scope_signal_requires_at_least_three_clauses():
    two_clauses = estimate_task_complexity("Add a new endpoint and write a test")
    assert "multi_step_scope" not in two_clauses.signals

    three_clauses = estimate_task_complexity(
        "Add a new endpoint, write a test, and update the documentation"
    )
    assert "multi_step_scope" in three_clauses.signals


def test_score_is_clamped_to_one():
    result = estimate_task_complexity(
        "Re-architect the system design, migrate the data model, rewrite the API "
        "endpoints across all modules end-to-end, upgrade every dependency, "
        "refactor and restructure everything, and write full test coverage"
    )
    assert result.score <= 1.0


def test_score_is_monotonic_in_matched_signal_count():
    single_signal = estimate_task_complexity("refactor the module")
    two_signals = estimate_task_complexity("refactor the module and migrate it")
    assert two_signals.score > single_signal.score


def test_pathologically_large_prompt_does_not_hang():
    """Regression test: before bounding the text these regex passes scan
    (see CHANGELOG.md), a ~25M-character prompt took ~9s to score because
    every signal phrase and the clause-split regex scanned it in full.
    A generous 2s ceiling here catches a real reintroduction of that
    unbounded scan without being a flaky timing assertion on normal-sized
    input."""
    import time

    huge_prompt = "implement " * 250_000  # ~2.5M characters
    start = time.perf_counter()
    estimate_task_complexity(huge_prompt)
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0

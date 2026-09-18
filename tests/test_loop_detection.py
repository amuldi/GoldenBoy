from goldenboy.core.loop_detection import LoopDetector


def test_first_attempt_does_not_stop(tmp_path):
    detector = LoopDetector(threshold=3, state_dir=str(tmp_path))
    result = detector.record("pytest", "test_x", "AssertionError")
    assert result.count == 1
    assert not result.should_stop


def test_same_signature_repeated_reaches_threshold(tmp_path):
    detector = LoopDetector(threshold=3, state_dir=str(tmp_path))
    for _ in range(2):
        result = detector.record("pytest", "test_x", "AssertionError")
    result = detector.record("pytest", "test_x", "AssertionError")
    assert result.count == 3
    assert result.should_stop


def test_below_threshold_continues(tmp_path):
    detector = LoopDetector(threshold=3, state_dir=str(tmp_path))
    detector.record("pytest", "test_x", "AssertionError")
    result = detector.record("pytest", "test_x", "AssertionError")
    assert result.count == 2
    assert not result.should_stop


def test_different_error_is_a_different_signature(tmp_path):
    """Same tool, same args, but a different error must not count toward
    the same loop -- it's a genuinely different failure."""
    detector = LoopDetector(threshold=2, state_dir=str(tmp_path))
    r1 = detector.record("pytest", "test_x", "AssertionError")
    r2 = detector.record("pytest", "test_x", "TypeError")
    assert r1.signature != r2.signature
    assert r1.count == 1
    assert r2.count == 1


def test_different_tool_is_a_different_signature(tmp_path):
    detector = LoopDetector(threshold=2, state_dir=str(tmp_path))
    r1 = detector.record("pytest", "test_x", "AssertionError")
    r2 = detector.record("mypy", "test_x", "AssertionError")
    assert r1.signature != r2.signature


def test_state_persists_across_instances(tmp_path):
    LoopDetector(threshold=5, state_dir=str(tmp_path)).record("pytest", "a", "b")
    detector2 = LoopDetector(threshold=5, state_dir=str(tmp_path))
    result = detector2.record("pytest", "a", "b")
    assert result.count == 2


def test_reset_clears_state(tmp_path):
    detector = LoopDetector(threshold=2, state_dir=str(tmp_path))
    detector.record("pytest", "a", "b")
    detector.reset()
    result = detector.record("pytest", "a", "b")
    assert result.count == 1


def test_status_lists_tracked_signatures(tmp_path):
    detector = LoopDetector(threshold=3, state_dir=str(tmp_path))
    detector.record("pytest", "a", "b")
    detector.record("mypy", "c", "d")
    status = detector.status()
    assert len(status) == 2


def test_default_threshold_comes_from_config(tmp_path):
    detector = LoopDetector(state_dir=str(tmp_path))
    assert detector.threshold == 3  # GoldenBoyConfig default

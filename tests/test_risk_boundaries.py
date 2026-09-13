from goldenboy.core.budget import Budget, UsageConfidence
from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.estimator import TaskEstimate
from goldenboy.core.risk import ExecutionMode, RiskEngine


def _engine(safety_margin=3.0, caution_ratio=0.5):
    return RiskEngine(config=GoldenBoyConfig(safety_margin=safety_margin, caution_ratio=caution_ratio))


def test_exhausted_boundary_is_inclusive():
    """Budget.is_exhausted() uses <=, so remaining exactly at the safety
    margin already counts as exhausted -- test both sides of that edge."""
    engine = _engine(safety_margin=3.0)
    estimate = TaskEstimate(estimated_percentage=1.0, confidence=1.0)

    at_margin = Budget(remaining_percentage=3.0, safety_margin=3.0)
    assert engine.assess(at_margin, estimate) == ExecutionMode.CRITICAL

    just_above = Budget(remaining_percentage=3.01, safety_margin=3.0)
    assert engine.assess(just_above, estimate) != ExecutionMode.CRITICAL


def test_required_exceeding_usable_is_limited_even_when_not_exhausted():
    engine = _engine(safety_margin=3.0)
    budget = Budget(remaining_percentage=20.0, safety_margin=3.0)  # usable = 17.0
    estimate = TaskEstimate(estimated_percentage=17.01, confidence=1.0)

    assert engine.assess(budget, estimate) == ExecutionMode.LIMITED


def test_caution_ratio_boundary_is_inclusive_toward_caution():
    """ratio < caution_ratio -> SAFE, ratio >= caution_ratio -> CAUTION."""
    engine = _engine(safety_margin=0.0, caution_ratio=0.5)
    budget = Budget(remaining_percentage=100.0, safety_margin=0.0)  # usable = 100

    exactly_at_ratio = TaskEstimate(estimated_percentage=50.0, confidence=1.0)
    assert engine.assess(budget, exactly_at_ratio) == ExecutionMode.CAUTION

    just_under_ratio = TaskEstimate(estimated_percentage=49.99, confidence=1.0)
    assert engine.assess(budget, just_under_ratio) == ExecutionMode.SAFE


def test_zero_usable_budget_with_nonzero_estimate_is_limited():
    engine = _engine(safety_margin=3.0)
    # remaining just above the margin so it's not CRITICAL, but usable ~ 0
    budget = Budget(remaining_percentage=3.01, safety_margin=3.0)
    estimate = TaskEstimate(estimated_percentage=5.0, confidence=1.0)

    assert engine.assess(budget, estimate) == ExecutionMode.LIMITED


def test_zero_required_against_a_sliver_of_usable_budget():
    """A zero-cost estimate against a nearly-exhausted-but-not-quite budget
    must resolve to SAFE, not divide by zero or misclassify. Note: usable
    can never be *exactly* zero here without is_exhausted() already having
    returned CRITICAL above (usable = max(0, remaining - margin), and
    is_exhausted is remaining <= margin) -- so the ratio branch's
    `else 1.0` fallback for usable == 0 is unreachable under the current
    Budget/RiskEngine invariants, not exercised by this test."""
    engine = _engine(safety_margin=3.0)
    budget = Budget(remaining_percentage=3.01, safety_margin=3.0)
    estimate = TaskEstimate(estimated_percentage=0.0, confidence=1.0)

    assert engine.assess(budget, estimate) == ExecutionMode.SAFE


def test_stale_confidence_prevents_a_false_safe_verdict():
    """The core safety property from the STALE lifecycle: a budget that
    would otherwise assess as SAFE must not be reported as SAFE once its
    source data is known to be aged out (source: an adapter's own aging
    logic sets confidence=STALE; RiskEngine's job is to not trust it)."""
    engine = _engine(safety_margin=0.0, caution_ratio=0.5)
    fresh = Budget(remaining_percentage=100.0, safety_margin=0.0, confidence=UsageConfidence.ESTIMATED)
    stale = Budget(remaining_percentage=100.0, safety_margin=0.0, confidence=UsageConfidence.STALE)
    estimate = TaskEstimate(estimated_percentage=10.0, confidence=1.0)  # would be SAFE

    assert engine.assess(fresh, estimate) == ExecutionMode.SAFE
    assert engine.assess(stale, estimate) == ExecutionMode.CAUTION


def test_stale_confidence_does_not_override_limited_or_critical():
    """STALE only ever downgrades an otherwise-SAFE verdict -- it must not
    mask (or worsen) a LIMITED/CRITICAL verdict that's already correct for
    other reasons; CRITICAL/LIMITED are hard limits independent of confidence."""
    engine = _engine(safety_margin=3.0, caution_ratio=0.5)

    exhausted = Budget(remaining_percentage=2.0, safety_margin=3.0, confidence=UsageConfidence.STALE)
    tiny_estimate = TaskEstimate(estimated_percentage=0.1, confidence=1.0)
    assert engine.assess(exhausted, tiny_estimate) == ExecutionMode.CRITICAL

    over_budget = Budget(remaining_percentage=20.0, safety_margin=3.0, confidence=UsageConfidence.STALE)
    huge_estimate = TaskEstimate(estimated_percentage=50.0, confidence=1.0)
    assert engine.assess(over_budget, huge_estimate) == ExecutionMode.LIMITED


def test_unknown_confidence_is_unaffected_by_the_stale_rule():
    """UNKNOWN is the long-standing Budget default (and the pre-refresh
    state of every real adapter) -- it must keep behaving exactly as before
    this feature existed, not be swept into the same downgrade as STALE."""
    engine = _engine(safety_margin=0.0, caution_ratio=0.5)
    budget = Budget(remaining_percentage=100.0, safety_margin=0.0)  # confidence defaults to UNKNOWN
    estimate = TaskEstimate(estimated_percentage=10.0, confidence=1.0)

    assert budget.confidence == UsageConfidence.UNKNOWN
    assert engine.assess(budget, estimate) == ExecutionMode.SAFE

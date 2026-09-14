from goldenboy.core.config import GoldenBoyConfig
from goldenboy.core.policies import (
    ComplexityOnlyPolicy,
    FixedThresholdPolicy,
    GoldenBoyPolicy,
    PolicyDecision,
    PolicyInput,
    UsageOnlyPolicy,
    default_baseline_policies,
)


def test_fixed_threshold_proceeds_above_threshold():
    policy = FixedThresholdPolicy(threshold_percentage=15.0)
    assert policy.decide(PolicyInput(20.0, 5.0)) == PolicyDecision.PROCEED


def test_fixed_threshold_stops_at_or_below_threshold():
    policy = FixedThresholdPolicy(threshold_percentage=15.0)
    assert policy.decide(PolicyInput(15.0, 5.0)) == PolicyDecision.STOP
    assert policy.decide(PolicyInput(10.0, 5.0)) == PolicyDecision.STOP


def test_complexity_only_ignores_budget():
    policy = ComplexityOnlyPolicy(max_cost_percentage=50.0)
    assert policy.decide(PolicyInput(remaining_percentage=1.0, estimated_cost_percentage=10.0)) == (
        PolicyDecision.PROCEED
    )
    assert policy.decide(PolicyInput(remaining_percentage=100.0, estimated_cost_percentage=60.0)) == (
        PolicyDecision.STOP
    )


def test_usage_only_uses_safety_margin():
    policy = UsageOnlyPolicy(config=GoldenBoyConfig(safety_margin=3.0))
    assert policy.decide(PolicyInput(3.0, 1.0)) == PolicyDecision.STOP
    assert policy.decide(PolicyInput(3.01, 1.0)) == PolicyDecision.PROCEED


def test_golden_boy_policy_proceeds_when_safe():
    policy = GoldenBoyPolicy(config=GoldenBoyConfig())
    assert policy.decide(PolicyInput(100.0, 10.0, usage_confidence="EXACT")) == PolicyDecision.PROCEED


def test_golden_boy_policy_stops_when_critical():
    policy = GoldenBoyPolicy(config=GoldenBoyConfig())
    assert policy.decide(PolicyInput(2.0, 10.0, usage_confidence="EXACT")) == PolicyDecision.STOP


def test_golden_boy_policy_stops_when_limited():
    policy = GoldenBoyPolicy(config=GoldenBoyConfig(safety_margin=3.0))
    assert policy.decide(PolicyInput(20.0, 17.01, usage_confidence="EXACT")) == PolicyDecision.STOP


def test_golden_boy_policy_handles_unrecognized_confidence_string_gracefully():
    policy = GoldenBoyPolicy(config=GoldenBoyConfig())
    # Must not raise even on a value that isn't a valid UsageConfidence.
    result = policy.decide(PolicyInput(100.0, 10.0, usage_confidence="not-a-real-confidence"))
    assert result in (PolicyDecision.PROCEED, PolicyDecision.STOP)


def test_default_baseline_policies_have_distinct_names():
    policies = default_baseline_policies()
    names = [p.name for p in policies]
    assert len(names) == len(set(names))
    assert len(policies) == 5

import json

import pytest

from goldenboy.protocol import (
    PROTOCOL_VERSION,
    GoldenBoyDecision,
    ProtocolError,
    RiskAssessment,
    TaskProfile,
    UsageSnapshot,
)


def _decision() -> GoldenBoyDecision:
    return GoldenBoyDecision.build(
        task=TaskProfile(
            task_type="bug_fix",
            task_type_confidence=0.7,
            complexity=0.3,
            complexity_label="MEDIUM",
            estimated_cost_percentage=25.0,
            estimated_cost_confidence=0.85,
            signals={"bug_fix:bug": 2},
        ),
        usage=UsageSnapshot(
            remaining_percentage=40.0, usable_percentage=37.0, source="mock", confidence="EXACT"
        ),
        risk=RiskAssessment(mode="CAUTION", reason_code="COST_TO_BUDGET_RATIO_AT_OR_ABOVE_CAUTION_THRESHOLD"),
        action="continue",
        confidence=0.72,
        reason="Task classified as bug_fix...",
        recommendation=["Keep going."],
    )


def test_round_trip_through_dict():
    decision = _decision()
    restored = GoldenBoyDecision.from_dict(decision.to_dict())
    assert restored == decision


def test_round_trip_through_json():
    decision = _decision()
    restored = GoldenBoyDecision.from_json(decision.to_json())
    assert restored == decision


def test_to_dict_is_plain_json_serializable():
    decision = _decision()
    # Must not raise -- every field is a plain str/float/list/dict.
    json.dumps(decision.to_dict())


def test_schema_version_is_stamped():
    decision = _decision()
    assert decision.schema_version == PROTOCOL_VERSION


def test_from_dict_rejects_missing_required_field():
    decision = _decision()
    data = decision.to_dict()
    del data["action"]

    with pytest.raises(ProtocolError, match="action"):
        GoldenBoyDecision.from_dict(data)


def test_from_dict_rejects_incompatible_major_version():
    decision = _decision()
    data = decision.to_dict()
    data["schema_version"] = "99.0.0"

    with pytest.raises(ProtocolError, match="not compatible"):
        GoldenBoyDecision.from_dict(data)


def test_from_dict_rejects_non_object_payload():
    with pytest.raises(ProtocolError, match="JSON object"):
        GoldenBoyDecision.from_dict([1, 2, 3])  # type: ignore[arg-type]


def test_from_json_rejects_invalid_json():
    with pytest.raises(ProtocolError, match="not valid JSON"):
        GoldenBoyDecision.from_json("{not valid json")


def test_nested_task_profile_missing_field_raises_protocol_error():
    decision = _decision()
    data = decision.to_dict()
    del data["task"]["task_type"]

    with pytest.raises(ProtocolError, match="TaskProfile"):
        GoldenBoyDecision.from_dict(data)


def test_recommendation_defaults_to_empty_list():
    decision = _decision()
    data = decision.to_dict()
    del data["recommendation"]

    restored = GoldenBoyDecision.from_dict(data)
    assert restored.recommendation == []

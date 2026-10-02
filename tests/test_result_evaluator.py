import json

import pytest

from goldenboy.adapters.base import GenerationResult
from goldenboy.core.result_evaluator import (
    EvaluationResult,
    evaluate_exit_status,
    evaluate_json_schema,
    evaluate_required_fields,
    evaluate_truncation,
)


def _gen_result(truncated: bool, stop_reason: str = "end_turn") -> GenerationResult:
    return GenerationResult(
        text="hello",
        input_tokens=10,
        output_tokens=20,
        stop_reason=stop_reason,
        truncated=truncated,
        latency_ms=12.0,
        model="claude-sonnet-4-5",
        provider="anthropic",
    )


SCHEMA = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
}


class TestEvaluateJsonSchema:
    def test_valid_json_sufficient(self):
        result = evaluate_json_schema(json.dumps({"name": "Ann", "age": 30}), SCHEMA)
        assert isinstance(result, EvaluationResult)
        assert result.sufficient is True
        assert result.evidence["parsed"] == {"name": "Ann", "age": 30}

    def test_not_json_insufficient(self):
        result = evaluate_json_schema("not json at all", SCHEMA)
        assert result.sufficient is False
        assert "json_error" in result.evidence
        assert result.evidence["raw_text"] == "not json at all"

    def test_missing_required_field(self):
        result = evaluate_json_schema(json.dumps({"name": "Ann"}), SCHEMA)
        assert result.sufficient is False
        assert result.evidence["missing_fields"] == ["age"]

    def test_wrong_type_field(self):
        result = evaluate_json_schema(json.dumps({"name": "Ann", "age": "thirty"}), SCHEMA)
        assert result.sufficient is False
        assert "age" in result.evidence["type_errors"]

    def test_not_an_object(self):
        result = evaluate_json_schema(json.dumps([1, 2, 3]), SCHEMA)
        assert result.sufficient is False
        assert result.evidence["expected_type"] == "object"


class TestEvaluateRequiredFields:
    def test_all_present(self):
        result = evaluate_required_fields("the cat sat on the mat", ["cat", "mat"])
        assert result.sufficient is True
        assert set(result.evidence["present"]) == {"cat", "mat"}

    def test_some_missing(self):
        result = evaluate_required_fields("the cat sat", ["cat", "dog"])
        assert result.sufficient is False
        assert result.evidence["missing"] == ["dog"]
        assert result.evidence["present"] == ["cat"]


class TestEvaluateTruncation:
    def test_not_truncated_sufficient(self):
        result = evaluate_truncation(_gen_result(truncated=False))
        assert result.sufficient is True
        assert result.evidence["truncation_condition"] == "not_truncated"

    def test_truncated_insufficient(self):
        result = evaluate_truncation(_gen_result(truncated=True, stop_reason="max_tokens"))
        assert result.sufficient is False
        assert result.evidence["truncation_condition"] == "truncated_output_limit"
        assert result.evidence["stop_reason"] == "max_tokens"


class TestEvaluateExitStatus:
    def test_zero_is_sufficient(self):
        result = evaluate_exit_status(0)
        assert result.sufficient is True
        assert result.evidence["exit_code"] == 0

    def test_nonzero_is_insufficient(self):
        result = evaluate_exit_status(1)
        assert result.sufficient is False
        assert result.evidence["exit_code"] == 1

    @pytest.mark.parametrize("code", [1, 2, 127, -1])
    def test_various_nonzero_codes(self, code):
        result = evaluate_exit_status(code)
        assert result.sufficient is False

"""Result Evaluator: deterministic, independently-callable checks on a
generation or execution result, each returning a shared `EvaluationResult`
with concrete evidence -- never a bare true/false.

Each function below is a narrow, pure check. There is no god-function that
runs "all the checks" and no orchestration here -- a caller composes
whichever evaluators are relevant to its own task and decides what to do
with the results (see `goldenboy.core.escalation` for the next step after
an insufficient result).

LLM-as-judge evaluation is deliberately NOT implemented in this stage.
The spec calls for using an LLM judge "only when necessary"; the
deterministic evaluators below (schema/field/truncation/exit-status) cover
the cases that don't need one. This is a scope decision, not an omission.

Schema validation dependency note: this repo ships zero required runtime
dependencies (see pyproject.toml `dependencies = []`), with `jsonschema`-
style libraries never previously pulled in as even an optional extra --
unlike `tiktoken`/`anthropic`/`openai`, there is no existing optional-extra
precedent for a JSON Schema validator here, and pulling one in for a single
narrow structural check (required fields + top-level type match) would be
disproportionate. `evaluate_json_schema` below therefore implements a small,
dependency-free structural check itself: required-field presence and
top-level JSON-Schema `type` matching, not full JSON Schema (no `$ref`,
`pattern`, `minimum`, nested `properties` recursion, etc.). This is
documented as a deliberate subset, not a bug.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from goldenboy.adapters.base import GenerationResult
from goldenboy.core.token_optimizer import TruncationCondition, classify_truncation


@dataclass(frozen=True)
class EvaluationResult:
    """The verdict of one evaluator call. `evidence` always carries the
    concrete data that backed the verdict (parsed value, missing fields,
    the truncation classification, the exit code, etc.) -- never an empty
    dict alongside a bare boolean."""

    sufficient: bool
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)


# JSON Schema `type` keyword -> Python type(s) it corresponds to.
_SCHEMA_TYPE_MAP: Dict[str, Any] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _check_type(value: Any, expected: str) -> bool:
    py_type = _SCHEMA_TYPE_MAP.get(expected)
    if py_type is None:
        return True  # unknown type keyword: don't fail on something we don't understand
    if expected == "integer" and isinstance(value, bool):
        return False  # bool is technically an int subclass; don't let it pass as integer
    if expected == "number" and isinstance(value, bool):
        return False
    return isinstance(value, py_type)


def evaluate_json_schema(text: str, schema: Dict[str, Any]) -> EvaluationResult:
    """Parse `text` as JSON and run a dependency-free structural check
    against `schema`: required-field presence (schema's `required` list)
    and top-level `properties[*].type` matching. Not full JSON Schema --
    see module docstring."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return EvaluationResult(
            sufficient=False,
            reason=f"Text is not valid JSON: {e}",
            evidence={"json_error": str(e), "raw_text": text},
        )

    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []

    if schema.get("type") == "object" or properties or required:
        if not isinstance(parsed, dict):
            return EvaluationResult(
                sufficient=False,
                reason=f"Parsed JSON is not an object (got {type(parsed).__name__}).",
                evidence={"parsed": parsed, "expected_type": "object"},
            )

    missing: List[str] = [field_name for field_name in required if field_name not in parsed]
    type_errors: Dict[str, str] = {}
    for field_name, field_schema in properties.items():
        if field_name not in parsed:
            continue
        expected_type = field_schema.get("type") if isinstance(field_schema, dict) else None
        if expected_type and not _check_type(parsed[field_name], expected_type):
            type_errors[field_name] = (
                f"expected {expected_type}, got {type(parsed[field_name]).__name__}"
            )

    if missing or type_errors:
        return EvaluationResult(
            sufficient=False,
            reason=(
                f"JSON does not satisfy schema: "
                f"{'missing fields ' + str(missing) if missing else ''}"
                f"{' ' if missing and type_errors else ''}"
                f"{'type errors ' + str(type_errors) if type_errors else ''}"
            ).strip(),
            evidence={"parsed": parsed, "missing_fields": missing, "type_errors": type_errors},
        )

    return EvaluationResult(
        sufficient=True,
        reason="JSON parsed and satisfies required fields/types in schema.",
        evidence={"parsed": parsed},
    )


def evaluate_required_fields(
    text: str, required_substrings_or_fields: Iterable[str]
) -> EvaluationResult:
    """Simpler presence check than `evaluate_json_schema`: does `text`
    contain each of `required_substrings_or_fields` as a literal
    substring? Useful when the caller doesn't have (or doesn't want to
    enforce) a full JSON schema -- e.g. checking a plain-text response
    mentions required keywords/field names."""
    required_list = list(required_substrings_or_fields)
    missing = [s for s in required_list if s not in text]
    present = [s for s in required_list if s in text]

    if missing:
        return EvaluationResult(
            sufficient=False,
            reason=f"Missing required substring(s): {missing}.",
            evidence={"missing": missing, "present": present, "required": required_list},
        )

    return EvaluationResult(
        sufficient=True,
        reason="All required substrings present.",
        evidence={"present": present, "required": required_list},
    )


def evaluate_truncation(result: GenerationResult) -> EvaluationResult:
    """Wraps `token_optimizer.classify_truncation`: a truncated result is
    never sufficient, regardless of what text it did produce."""
    condition = classify_truncation(result)
    if condition is TruncationCondition.TRUNCATED_OUTPUT_LIMIT:
        return EvaluationResult(
            sufficient=False,
            reason="Generation was truncated by the output-length limit.",
            evidence={
                "truncation_condition": condition.value,
                "stop_reason": result.stop_reason,
                "output_tokens": result.output_tokens,
                "model": result.model,
                "provider": result.provider,
            },
        )
    return EvaluationResult(
        sufficient=True,
        reason="Generation was not truncated.",
        evidence={
            "truncation_condition": condition.value,
            "stop_reason": result.stop_reason,
            "output_tokens": result.output_tokens,
        },
    )


def evaluate_exit_status(exit_code: int) -> EvaluationResult:
    """Zero is success; anything else is a failing exit status, same
    convention as `goldenboy.core.snapshot.VerifyStepResult.passed`
    (`passed = proc.returncode == 0`) -- this function doesn't duplicate
    that dataclass, it just applies the same rule to a bare exit code for
    callers that only have the integer (e.g. not running through
    snapshot.py's verification harness)."""
    sufficient = exit_code == 0
    return EvaluationResult(
        sufficient=sufficient,
        reason=(
            "Process exited successfully (code 0)."
            if sufficient
            else f"Process exited with non-zero status {exit_code}."
        ),
        evidence={"exit_code": exit_code},
    )

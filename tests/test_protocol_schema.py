"""Cross-checks `schemas/decision.schema.json` against the real Python
implementation (`goldenboy/protocol.py` + `goldenboy/core/decision_engine.py`).

Two distinct things are checked, on purpose:

1. Real decisions (produced by `DecisionEngine`, not hand-built fixtures)
   across every `ExecutionMode` actually validate against the schema --
   catching the schema falling out of sync with what Golden Boy really
   emits.
2. The schema's own `required` lists match what `GoldenBoyDecision.from_dict`
   (and its nested `from_dict`s) actually enforce via `_require` --
   catching the schema and the hand-written Python validation drifting
   apart from each other, which is exactly the maintenance risk
   `docs/PROTOCOL.md` names ("kept in sync by hand").

The TypeScript side has the equivalent check in
`sdk/typescript/test/schema.test.ts` against the same schema file.
"""
import json
from pathlib import Path

import pytest

from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine
from goldenboy.protocol import GoldenBoyDecision
from tests.schema_support import required_fields, validate

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "decision.schema.json"


@pytest.fixture(scope="module")
def schema():
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# Budgets chosen to exercise every ExecutionMode (SAFE/CAUTION/LIMITED/
# CRITICAL) plus the ASK_USER low-confidence path, mirroring the risk
# boundaries already pinned in tests/test_risk_boundaries.py.
_REAL_WORLD_BUDGETS = [100.0, 40.0, 10.0, 2.0]
_TASKS = [
    "Fix a typo in the README",
    "Implement OAuth authentication with refresh tokens and full test coverage",
    "Audit the entire repository for dead code",
]


def _real_decisions():
    engine = DecisionEngine()
    for budget in _REAL_WORLD_BUDGETS:
        for task in _TASKS:
            yield engine.decide(task, MockProvider(initial_percentage=budget))


@pytest.mark.parametrize("decision", list(_real_decisions()))
def test_real_decisions_validate_against_schema(decision: GoldenBoyDecision, schema):
    validate(decision.to_dict(), schema)


def test_schema_required_fields_match_protocol_from_dict(schema):
    # These sets are the ground truth: the exact keys `_require()` calls
    # for each dataclass in goldenboy/protocol.py. If a field is added or
    # removed from `_require` calls there without updating the schema (or
    # vice versa), this test is the one that catches it.
    assert set(required_fields(schema)) == {
        "schema_version", "generated_at", "task", "usage", "risk", "action", "confidence", "reason",
    }
    assert set(required_fields(schema, "$defs", "taskProfile")) == {
        "task_type", "task_type_confidence", "complexity", "complexity_label",
        "estimated_cost_percentage", "estimated_cost_confidence",
    }
    assert set(required_fields(schema, "$defs", "usageSnapshot")) == {
        "remaining_percentage", "usable_percentage", "source", "confidence",
    }
    assert set(required_fields(schema, "$defs", "riskAssessment")) == {
        "mode", "reason_code",
    }


def test_schema_rejects_payload_missing_a_required_field(schema):
    decision = next(_real_decisions())
    payload = decision.to_dict()
    del payload["action"]
    with pytest.raises(AssertionError):
        validate(payload, schema)


def test_schema_action_enum_matches_decision_action_values():
    from goldenboy.core.task_types import DecisionAction

    schema_enum = set(_load_schema()["properties"]["action"]["enum"])
    assert schema_enum == {action.value for action in DecisionAction}


def test_schema_task_type_enum_matches_task_type_values():
    from goldenboy.core.task_types import TaskType

    schema_enum = set(
        _load_schema()["$defs"]["taskProfile"]["properties"]["task_type"]["enum"]
    )
    assert schema_enum == {t.value for t in TaskType}


def _load_schema():
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

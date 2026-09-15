/**
 * Cross-language schema compatibility check: `schemas/decision.schema.json`
 * (the shared, hand-authored source of truth) vs. what `parseDecision`
 * actually enforces in this package. The Python side has the equivalent
 * check in `tests/test_protocol_schema.py`.
 *
 * Rather than hardcoding a second copy of the schema's `required` lists
 * here (which could itself drift from the schema file), each required
 * field is read directly out of the schema JSON and exercised: build a
 * valid payload, delete that field, and assert `parseDecision` rejects it.
 * That way a field added to the schema but not enforced by `parseDecision`
 * (or vice versa) fails this test without a second list to maintain.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { ProtocolError } from "../src/errors.js";
import { PROTOCOL_VERSION } from "../src/types.js";
import { parseDecision } from "../src/validate.js";

// dist/test/schema.test.js -> dist -> typescript -> sdk -> repo root
const schemaPath = fileURLToPath(
  new URL("../../../../schemas/decision.schema.json", import.meta.url),
);
const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));

function validPayload(): Record<string, unknown> {
  return {
    schema_version: PROTOCOL_VERSION,
    generated_at: "2026-09-14T00:00:00+00:00",
    task: {
      task_type: "bug_fix",
      task_type_confidence: 0.7,
      complexity: 0.2,
      complexity_label: "LOW",
      estimated_cost_percentage: 10.0,
      estimated_cost_confidence: 0.85,
      signals: { "bug_fix:bug": 2 },
    },
    usage: {
      remaining_percentage: 50.0,
      usable_percentage: 47.0,
      source: "mock",
      confidence: "EXACT",
    },
    risk: { mode: "SAFE", reason_code: "COST_TO_BUDGET_RATIO_BELOW_CAUTION_THRESHOLD", ratio: 0.21 },
    action: "run",
    confidence: 0.9,
    reason: "Task classified as bug_fix...",
    recommendation: ["Proceed with the task as scoped."],
  };
}

test("every schema-required top-level field is enforced by parseDecision", () => {
  for (const field of schema.required as string[]) {
    const payload = validPayload();
    delete payload[field];
    assert.throws(
      () => parseDecision(payload),
      ProtocolError,
      `expected parseDecision to reject a payload missing top-level '${field}'`,
    );
  }
});

test("every schema-required task field is enforced by parseDecision", () => {
  for (const field of schema.$defs.taskProfile.required as string[]) {
    const payload = validPayload();
    delete (payload.task as Record<string, unknown>)[field];
    assert.throws(
      () => parseDecision(payload),
      ProtocolError,
      `expected parseDecision to reject a task payload missing '${field}'`,
    );
  }
});

test("every schema-required usage field is enforced by parseDecision", () => {
  for (const field of schema.$defs.usageSnapshot.required as string[]) {
    const payload = validPayload();
    delete (payload.usage as Record<string, unknown>)[field];
    assert.throws(
      () => parseDecision(payload),
      ProtocolError,
      `expected parseDecision to reject a usage payload missing '${field}'`,
    );
  }
});

test("every schema-required risk field is enforced by parseDecision", () => {
  for (const field of schema.$defs.riskAssessment.required as string[]) {
    const payload = validPayload();
    delete (payload.risk as Record<string, unknown>)[field];
    assert.throws(
      () => parseDecision(payload),
      ProtocolError,
      `expected parseDecision to reject a risk payload missing '${field}'`,
    );
  }
});

// The DecisionAction/TaskType unions in types.ts only exist at compile
// time, so unlike the required-field checks above, these enum lists are a
// second, hand-kept copy -- same convention as types.ts's own header
// comment. A mismatch here means schema.json and types.ts have drifted.
const EXPECTED_ACTIONS = ["run", "continue", "reduce_scope", "finish", "verify", "stop", "ask_user"];
const EXPECTED_TASK_TYPES = [
  "implementation", "bug_fix", "refactor", "testing", "debugging", "documentation",
  "research", "dependency_change", "architecture_change", "code_review",
  "performance_optimization", "release", "unknown",
];

test("schema action enum matches the TypeScript DecisionAction union", () => {
  assert.deepEqual([...schema.properties.action.enum].sort(), [...EXPECTED_ACTIONS].sort());
});

test("schema task_type enum matches the TypeScript TaskType union", () => {
  assert.deepEqual(
    [...schema.$defs.taskProfile.properties.task_type.enum].sort(),
    [...EXPECTED_TASK_TYPES].sort(),
  );
});

test("a fully valid payload built from the schema's own required fields parses cleanly", () => {
  const decision = parseDecision(validPayload());
  assert.equal(decision.action, "run");
});

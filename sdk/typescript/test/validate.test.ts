import assert from "node:assert/strict";
import { test } from "node:test";

import { ProtocolError } from "../src/errors.js";
import { PROTOCOL_VERSION } from "../src/types.js";
import { parseDecision, parseDecisionJson } from "../src/validate.js";

function validPayload() {
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

test("parses a well-formed decision payload", () => {
  const decision = parseDecision(validPayload());
  assert.equal(decision.task.task_type, "bug_fix");
  assert.equal(decision.action, "run");
  assert.equal(decision.risk.mode, "SAFE");
});

test("round-trips through JSON.stringify/parseDecisionJson", () => {
  const original = parseDecision(validPayload());
  const restored = parseDecisionJson(JSON.stringify(original));
  assert.deepEqual(restored, original);
});

test("rejects a missing required field", () => {
  const payload = validPayload() as Record<string, unknown>;
  delete payload.action;
  assert.throws(() => parseDecision(payload), ProtocolError);
});

test("rejects a missing nested field", () => {
  const payload = validPayload();
  delete (payload.task as Record<string, unknown>).task_type;
  assert.throws(() => parseDecision(payload), (err: unknown) => {
    return err instanceof ProtocolError && /TaskProfile/.test((err as Error).message);
  });
});

test("rejects an incompatible major schema version", () => {
  const payload = validPayload();
  payload.schema_version = "99.0.0";
  assert.throws(() => parseDecision(payload), (err: unknown) => {
    return err instanceof ProtocolError && /not compatible/.test((err as Error).message);
  });
});

test("rejects a non-object payload", () => {
  assert.throws(() => parseDecision([1, 2, 3]), ProtocolError);
  assert.throws(() => parseDecision(null), ProtocolError);
  assert.throws(() => parseDecision("a string"), ProtocolError);
});

test("rejects invalid JSON text", () => {
  assert.throws(() => parseDecisionJson("{not valid json"), ProtocolError);
});

test("recommendation defaults to an empty array when absent", () => {
  const payload = validPayload() as Record<string, unknown>;
  delete payload.recommendation;
  const decision = parseDecision(payload);
  assert.deepEqual(decision.recommendation, []);
});

test("signals defaults to an empty object when absent", () => {
  const payload = validPayload();
  delete (payload.task as Record<string, unknown>).signals;
  const decision = parseDecision(payload);
  assert.deepEqual(decision.task.signals, {});
});

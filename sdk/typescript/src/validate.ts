import { ProtocolError } from "./errors.js";
import type { GoldenBoyDecision, RiskAssessment, TaskProfile, UsageSnapshot } from "./types.js";
import { PROTOCOL_VERSION } from "./types.js";

function major(version: string): string {
  return version.split(".", 1)[0] ?? version;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireField(obj: Record<string, unknown>, key: string, context: string): unknown {
  if (!(key in obj)) {
    throw new ProtocolError(`${context} is missing required field '${key}'.`);
  }
  return obj[key];
}

function parseTaskProfile(raw: unknown): TaskProfile {
  if (!isPlainObject(raw)) {
    throw new ProtocolError(`TaskProfile payload must be an object, got ${typeof raw}.`);
  }
  return {
    task_type: requireField(raw, "task_type", "TaskProfile") as string,
    task_type_confidence: requireField(raw, "task_type_confidence", "TaskProfile") as number,
    complexity: requireField(raw, "complexity", "TaskProfile") as number,
    complexity_label: requireField(raw, "complexity_label", "TaskProfile") as string,
    estimated_cost_percentage: requireField(raw, "estimated_cost_percentage", "TaskProfile") as number,
    estimated_cost_confidence: requireField(raw, "estimated_cost_confidence", "TaskProfile") as number,
    signals: (raw.signals as Record<string, number> | undefined) ?? {},
    complexity_signals: (raw.complexity_signals as string[] | undefined) ?? [],
    secondary_task_types: (raw.secondary_task_types as string[] | undefined) ?? [],
  };
}

function parseUsageSnapshot(raw: unknown): UsageSnapshot {
  if (!isPlainObject(raw)) {
    throw new ProtocolError(`UsageSnapshot payload must be an object, got ${typeof raw}.`);
  }
  return {
    remaining_percentage: requireField(raw, "remaining_percentage", "UsageSnapshot") as number,
    usable_percentage: requireField(raw, "usable_percentage", "UsageSnapshot") as number,
    source: requireField(raw, "source", "UsageSnapshot") as string,
    confidence: requireField(raw, "confidence", "UsageSnapshot") as string,
  };
}

function parseRiskAssessment(raw: unknown): RiskAssessment {
  if (!isPlainObject(raw)) {
    throw new ProtocolError(`RiskAssessment payload must be an object, got ${typeof raw}.`);
  }
  return {
    mode: requireField(raw, "mode", "RiskAssessment") as string,
    reason_code: requireField(raw, "reason_code", "RiskAssessment") as string,
    ratio: (raw.ratio as number | null | undefined) ?? null,
  };
}

/** Strictly validates and parses a raw decoded-JSON value into a
 * `GoldenBoyDecision`, throwing `ProtocolError` (never a raw TypeError) on
 * a missing field or an incompatible major schema version — the same
 * contract `goldenboy.protocol.GoldenBoyDecision.from_dict` enforces on
 * the Python side. */
export function parseDecision(raw: unknown): GoldenBoyDecision {
  const context = "GoldenBoyDecision";
  if (!isPlainObject(raw)) {
    throw new ProtocolError(`${context} payload must be a JSON object, got ${typeof raw}.`);
  }

  const version = requireField(raw, "schema_version", context) as string;
  if (major(version) !== major(PROTOCOL_VERSION)) {
    throw new ProtocolError(
      `${context} payload has schema_version=${JSON.stringify(version)}, which is not compatible ` +
        `with this SDK's protocol major version (${PROTOCOL_VERSION}). Upgrade the ` +
        "reader/writer so both sides agree on a major version.",
    );
  }

  return {
    schema_version: version,
    generated_at: requireField(raw, "generated_at", context) as string,
    task: parseTaskProfile(requireField(raw, "task", context)),
    usage: parseUsageSnapshot(requireField(raw, "usage", context)),
    risk: parseRiskAssessment(requireField(raw, "risk", context)),
    action: requireField(raw, "action", context) as string,
    confidence: requireField(raw, "confidence", context) as number,
    reason: requireField(raw, "reason", context) as string,
    recommendation: (raw.recommendation as string[] | undefined) ?? [],
  };
}

/** Parses a raw JSON string (e.g. `goldenboy analyze --json`'s stdout)
 * into a `GoldenBoyDecision`. Throws `ProtocolError` on invalid JSON or a
 * payload that fails `parseDecision`. */
export function parseDecisionJson(text: string): GoldenBoyDecision {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (e) {
    throw new ProtocolError(`GoldenBoyDecision payload is not valid JSON: ${(e as Error).message}`);
  }
  return parseDecision(raw);
}

/**
 * TypeScript mirror of the Golden Boy Protocol (see `goldenboy/protocol.py`
 * in the Python package — that module is the source of truth; this file
 * must stay in sync with it by hand, the same way `skills/goldenboy/SKILL.md`
 * stays in sync with `goldenboy.core.risk.ExecutionMode`).
 *
 * These are pure data shapes. No business logic (cost estimation, risk
 * assessment, task classification) lives here or anywhere else in this
 * SDK — see `client.ts` for why.
 */

/** Bump the major segment for a breaking change; the client only refuses a
 * payload whose *major* version it doesn't recognize (see `validate.ts`).
 * 1.1.0: additive `TaskProfile.complexity_signals` (see that field below). */
export const PROTOCOL_VERSION = "1.1.0";

export type TaskType =
  | "implementation"
  | "bug_fix"
  | "refactor"
  | "testing"
  | "debugging"
  | "documentation"
  | "research"
  | "dependency_change"
  | "architecture_change"
  | "code_review"
  | "performance_optimization"
  | "release"
  | "unknown";

export type ExecutionMode = "SAFE" | "CAUTION" | "LIMITED" | "CRITICAL";

export type DecisionAction =
  | "run"
  | "continue"
  | "reduce_scope"
  | "finish"
  | "verify"
  | "stop"
  | "ask_user";

export type UsageConfidence = "EXACT" | "ESTIMATED" | "STALE" | "UNKNOWN";

export interface TaskProfile {
  task_type: TaskType | string;
  task_type_confidence: number;
  /** Heuristic weighted-signal strength in [0, 1] from
   * `goldenboy.core.complexity` — NOT a calibrated probability. */
  complexity: number;
  complexity_label: "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH" | string;
  estimated_cost_percentage: number;
  estimated_cost_confidence: number;
  signals: Record<string, number>;
  /** Names of fixed complexity signals that fired (e.g. "architecture_keyword").
   * Added in PROTOCOL_VERSION 1.1.0; absent/empty on older payloads. */
  complexity_signals?: string[];
  /** Other task types that also scored meaningfully alongside `task_type`.
   * Added in PROTOCOL_VERSION 1.1.0; absent/empty on older payloads. */
  secondary_task_types?: (TaskType | string)[];
}

export interface UsageSnapshot {
  remaining_percentage: number;
  usable_percentage: number;
  source: string;
  confidence: UsageConfidence | string;
}

export interface RiskAssessment {
  mode: ExecutionMode | string;
  reason_code: string;
  ratio: number | null;
}

/** The single, stable output shape Golden Boy produces for a task — what
 * `goldenboy analyze --json` prints and what `GoldenBoyClient.analyze()`
 * returns. Every field is something Golden Boy actually measured for that
 * call; nothing here is a client-side guess. */
export interface GoldenBoyDecision {
  schema_version: string;
  generated_at: string;
  task: TaskProfile;
  usage: UsageSnapshot;
  risk: RiskAssessment;
  action: DecisionAction | string;
  confidence: number;
  reason: string;
  recommendation: string[];
}

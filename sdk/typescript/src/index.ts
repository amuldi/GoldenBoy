export { GoldenBoyClient } from "./client.js";
export type { AnalyzeOptions, GoldenBoyClientOptions } from "./client.js";
export { CliError, GoldenBoyError, ProtocolError } from "./errors.js";
export {
  PROTOCOL_VERSION,
  type DecisionAction,
  type ExecutionMode,
  type GoldenBoyDecision,
  type RiskAssessment,
  type TaskProfile,
  type TaskType,
  type UsageConfidence,
  type UsageSnapshot,
} from "./types.js";
export { parseDecision, parseDecisionJson } from "./validate.js";

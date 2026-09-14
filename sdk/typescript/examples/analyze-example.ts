/**
 * Run with: npm run build && node dist/examples/analyze-example.js
 * (requires `goldenboy` on PATH — `pip install goldenboy`, or set
 * GOLDENBOY_BIN to a specific interpreter's console script.)
 */
import { GoldenBoyClient, CliError } from "../src/index.js";

async function main() {
  const client = new GoldenBoyClient({ binaryPath: process.env.GOLDENBOY_BIN ?? "goldenboy" });

  const decision = await client.analyze(
    "Refactor the authentication system and update tests",
    { budget: 15 }, // e.g. 15% of the agent's usage budget remaining
  );

  console.log(`Task type:  ${decision.task.task_type} (${decision.task.complexity_label} complexity)`);
  console.log(`Risk mode:  ${decision.risk.mode} (${decision.risk.reason_code})`);
  console.log(`Decision:   ${decision.action.toUpperCase()} (confidence: ${decision.confidence.toFixed(2)})`);
  console.log(`Reason:     ${decision.reason}`);
  if (decision.recommendation.length > 0) {
    console.log("Recommendation:");
    for (const step of decision.recommendation) console.log(`  - ${step}`);
  }
}

main().catch((err) => {
  if (err instanceof CliError) {
    console.error(`Golden Boy CLI error: ${err.message}`);
    process.exitCode = 1;
    return;
  }
  throw err;
});

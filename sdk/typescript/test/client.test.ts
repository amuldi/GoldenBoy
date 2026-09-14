/**
 * Integration tests against the *real* `goldenboy` CLI — not a mock, not a
 * fixture. Per project rule "no fake integrations": if the CLI genuinely
 * isn't installed/reachable in this environment, each test skips itself
 * with an explicit reason rather than silently passing or fabricating a
 * response.
 *
 * Point GOLDENBOY_BIN at a specific interpreter's console script (e.g. a
 * venv) if `goldenboy` isn't on PATH; see sdk/typescript/README.md.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { GoldenBoyClient } from "../src/client.js";
import { CliError } from "../src/errors.js";

const binaryPath = process.env.GOLDENBOY_BIN ?? "goldenboy";

async function skipIfUnavailable(t: import("node:test").TestContext): Promise<GoldenBoyClient | undefined> {
  const client = new GoldenBoyClient({ binaryPath });
  try {
    await client.status(100);
  } catch (e) {
    if (e instanceof CliError && e.exitCode === null) {
      t.skip(`goldenboy CLI not found at '${binaryPath}' — set GOLDENBOY_BIN or 'pip install -e .' first`);
      return undefined;
    }
    throw e;
  }
  return client;
}

test("analyze() returns a real, protocol-validated decision from the actual CLI", async (t) => {
  const client = await skipIfUnavailable(t);
  if (!client) return;

  const decision = await client.analyze("Fix a bug in the login flow", { budget: 50 });

  assert.equal(decision.task.task_type, "bug_fix");
  assert.ok(decision.confidence >= 0 && decision.confidence <= 1);
  assert.ok(decision.reason.length > 0);
  assert.ok(["run", "continue", "reduce_scope", "finish", "verify", "stop", "ask_user"].includes(decision.action));
});

test("analyze() reflects a low budget as a stricter risk mode", async (t) => {
  const client = await skipIfUnavailable(t);
  if (!client) return;

  const decision = await client.analyze("Fix a bug", { budget: 2 });
  assert.equal(decision.risk.mode, "CRITICAL");
  assert.equal(decision.action, "stop");
});

test("status() returns real budget numbers matching the requested mock budget", async (t) => {
  const client = await skipIfUnavailable(t);
  if (!client) return;

  const status = await client.status(42);
  assert.equal(status.remaining_percentage, 42);
  assert.equal(status.source, "mock");
});

test("doctor() never leaks an API key value even when one is set", async (t) => {
  const client = await skipIfUnavailable(t);
  if (!client) return;

  const previous = process.env.ANTHROPIC_API_KEY;
  process.env.ANTHROPIC_API_KEY = "sk-ant-should-never-appear-in-sdk-output";
  try {
    const doctor = await client.doctor();
    const serialized = JSON.stringify(doctor);
    assert.ok(!serialized.includes("sk-ant-should-never-appear-in-sdk-output"));
  } finally {
    if (previous === undefined) delete process.env.ANTHROPIC_API_KEY;
    else process.env.ANTHROPIC_API_KEY = previous;
  }
});

test("an unknown binary path raises CliError, not a raw exception", async () => {
  const client = new GoldenBoyClient({ binaryPath: "definitely-not-a-real-binary-xyz" });
  await assert.rejects(() => client.status(50), CliError);
});

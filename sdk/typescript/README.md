# @goldenboy/sdk

A lightweight TypeScript client for the [Golden Boy Protocol](../../docs/PROTOCOL.md).

This SDK does **not** reimplement Golden Boy's cost estimation, task
classification, or risk logic in TypeScript. It spawns the real `goldenboy`
CLI (`--json` output) and parses its response through the same strict
protocol validation the Python side uses (`goldenboy.protocol.GoldenBoyDecision`),
so a TypeScript-based agent gets the exact same decision a Python caller
would — never a second, potentially-drifting implementation.

## Requirements

- Node.js >= 18
- The `goldenboy` CLI available (`pip install goldenboy`, or an editable
  install from the repo root: `pip install -e .`), either on `PATH` or
  pointed to explicitly via `binaryPath` / `GOLDENBOY_BIN`.

## Install (from this repo)

```bash
cd sdk/typescript
npm install
npm run build
```

## Usage

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // uses `goldenboy` from PATH

const decision = await client.analyze(
  "Refactor the authentication system and update tests",
  { budget: 15 }, // percent of usage remaining
);

console.log(decision.action);       // "reduce_scope" | "run" | "continue" | ...
console.log(decision.confidence);   // 0.0-1.0
console.log(decision.reason);       // human-readable, built from real measurements
```

If `goldenboy` isn't on `PATH` (e.g. a specific virtualenv), point the
client at it directly:

```ts
const client = new GoldenBoyClient({ binaryPath: "/path/to/venv/bin/goldenboy" });
```

## API

- `new GoldenBoyClient(options?)` — `{ binaryPath?, cwd?, timeoutMs? }`.
- `client.analyze(task, { budget?, progress? })` → `Promise<GoldenBoyDecision>`
- `client.status(budget?)` → `Promise<{ remaining_percentage, usable_percentage, is_exhausted, source, confidence, checkpoint }>`
- `client.doctor()` → `Promise<{ python, dependencies, config, checkpoint }>` (never includes an API key's value)
- `client.validate()` → `Promise<unknown>` (the `goldenboy validate --json` payload; throws `CliError` on a broken config or POOR data quality, matching the CLI's own exit code)
- `client.replay(datasetPath?)` → `Promise<unknown>` (the `goldenboy replay --json` payload)

All methods throw:
- `CliError` — the CLI exited non-zero, or the binary couldn't be found/spawned (`exitCode`/`stderr` attached).
- `ProtocolError` — the CLI's stdout wasn't valid JSON, or didn't match the expected schema/version.

See `src/types.ts` for the full `GoldenBoyDecision` shape and
`examples/analyze-example.ts` for a runnable example.

## Testing

```bash
npm test
```

Runs the full suite via Node's built-in test runner (`node:test` — no
external test framework dependency). The `client.test.ts` suite exercises
the *real* `goldenboy` CLI (no mocking): each test skips itself with an
explicit reason if the CLI can't be found, rather than silently passing.
Set `GOLDENBOY_BIN` to point at a specific install if `goldenboy` isn't on
`PATH`.

## Design notes

- **No duplicated business logic.** Every real decision comes from the
  Python CLI; this package is a typed transport + validation layer only.
- **No HTTP server.** Communicates over a spawned child process and stdout,
  matching the project's "avoid a server if local IPC is sufficient"
  principle — there's no daemon to keep running or port to manage.
- **Kept lightweight.** Zero runtime dependencies; `typescript` and
  `@types/node` are the only devDependencies.

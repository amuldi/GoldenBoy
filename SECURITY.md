# Security Policy

## What Golden Boy stores

Golden Boy is local-first and does not phone home. The only state it
persists is a checkpoint file at `.goldenboy/checkpoint.json` (created next
to wherever you run it), containing:

- the task name you gave it
- the execution mode at save time (SAFE/CAUTION/LIMITED/CRITICAL)
- a budget snapshot (remaining percentage, source, confidence) — never the
  underlying API key or raw provider response
- the list of `ExecutionUnit`s (id, description, priority, status, cost)

`.goldenboy/` is gitignored by default. Nothing else is written to disk.

## Credentials

`AnthropicAdapter` and `OpenAIAdapter` read `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY` from the environment (see `.env.example`). Golden Boy:

- never writes an API key to the checkpoint file, logs, or stdout
- never includes a key in an exception message it raises
- makes no network call itself except the explicit `refresh_usage()` probe
  on those two adapters, which sends a 1-token throwaway request solely to
  read rate-limit response headers

If you find a place where a key or token *does* leak into a log, error
message, or persisted file, that's a bug — please report it (see below)
rather than opening a public issue.

## Untrusted input handling

Golden Boy parses two on-disk JSON files: `.goldenboy/config.json` and `.goldenboy/checkpoint.json`.
Both are read with plain `json.load` (no `eval`, `pickle`, or `yaml.load` — verified: the shipped
`goldenboy` package contains no `subprocess`, `os.system`, `eval`, `exec`, `pickle`, or `yaml` calls at
all). A malformed or hostile file can only ever cause a `ConfigError`/`CheckpointError` naming the
problem — it cannot execute code or write outside `.goldenboy/`. Config/checkpoint paths are fixed
relative to the current working directory and are not built from any external or remote input, so there
is no path-traversal surface via a CLI argument today; this would need re-review if a future version
accepts a user-supplied path for either file.

## Telemetry

None. Golden Boy does not collect or transmit usage analytics.

## Reporting a vulnerability

Please report security issues privately rather than as a public GitHub
issue. Open a [GitHub Security Advisory](../../security/advisories/new) on
this repository, or, if that's unavailable, open an issue asking a
maintainer to contact you privately rather than describing the issue in
the open. Include:

- the affected version/commit
- a minimal reproduction
- the potential impact as you understand it

There is currently no bug bounty program.

## Supported versions

Golden Boy is pre-1.0 (`0.1.x`). Security fixes land on `main`; there is no
separate maintenance branch yet.

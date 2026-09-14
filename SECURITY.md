# Security Policy

## What Golden Boy stores

Golden Boy is local-first and does not phone home. All state lives under
`.goldenboy/` (created next to wherever you run it), which is gitignored by
default and never sent anywhere:

- **`checkpoint.json`** — the task name you gave it, the execution mode at
  save time (SAFE/CAUTION/LIMITED/CRITICAL), a budget snapshot (remaining
  percentage, source, confidence — never the underlying API key or raw
  provider response), and the list of `ExecutionUnit`s (id, description,
  priority, status, cost).
- **`history.jsonl`** — one line per `budget_aware_execution`-decorated
  call (see `goldenboy.core.history.TaskEvent`), used by
  `goldenboy.analytics`/`goldenboy.replay`. It records the classified task
  type, cost/usage numbers, decision mode, and outcome — **never the task's
  raw prompt text**, only its character length and a truncated SHA-256
  hash (`TaskEvent.prompt_hash`), which cannot be reversed back into the
  original text. Pass your own `HistoryStore` (or one whose `append` is a
  no-op) to redirect or disable this.

Nothing else is written to disk, and no file above ever contains an API
key, prompt text, or raw provider response body.

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

Golden Boy parses on-disk files under `.goldenboy/`: `config.json`, `checkpoint.json`, and
`history.jsonl`. All are read with plain `json.load`/`json.loads` (no `eval`, `pickle`, or `yaml.load` —
verified: the shipped `goldenboy` package contains no `subprocess`, `os.system`, `eval`, `exec`, `pickle`,
or `yaml` calls at all). A malformed or hostile `config.json`/`checkpoint.json` can only ever cause a
`ConfigError`/`CheckpointError` naming the problem; a malformed line in `history.jsonl` is silently
skipped and counted (see `HistoryStore.load_events`), never raised as a fatal error, so one corrupted
line cannot block reading the rest of a real history. None of the three can execute code or write outside
`.goldenboy/`. Their paths are fixed relative to the current working directory and are not built from any
external or remote input, so there is no path-traversal surface via a CLI argument today; this would need
re-review if a future version accepts a user-supplied path for any of them.

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

Golden Boy is at `1.x`. Security fixes land on `main`; there is no separate
maintenance branch yet.

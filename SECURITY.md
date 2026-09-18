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
- **`telemetry.jsonl`** — one line per `goldenboy report` call
  (`goldenboy.core.telemetry.ExecutionTelemetry`): estimated vs. actual
  token/cost figures and outcome, never raw prompt or diff text.
- **`policy.json`** (optional, user-authored) — Policy Engine rule config
  (`goldenboy.core.governance.PolicyConfig`): denied/approval tool and
  command patterns, protected path patterns, budget thresholds. No secrets
  belong in this file and none are read from it.
- **`router.json`** (optional, user-authored) — `goldenboy.core.router.
  RouterConfig`'s tier-to-model-name mapping. Model names only, e.g.
  `"cheap": "org/small-model"` — never a credential.
- **`audit.jsonl`** — one line per governance decision
  (`goldenboy.core.audit.AuditEntry`): action, tool, policy verdict,
  estimated/actual cost, result, and (if present) an error message. The
  `error` field and any string in `extra` are passed through
  `goldenboy.core.redaction.redact_secrets` before being written — see
  "Secret redaction" below.
- **`spending.jsonl`** — one line per recorded spend
  (`goldenboy.core.spending.SpendEntry`): a label, estimated/actual token
  counts, optional task type. No prompt text.
- **`session_start`** — a single ISO-8601 timestamp
  (`goldenboy.core.spending.SessionMarker`) marking when the current
  "session" window began. Nothing else.
- **`loop_state.json`** — `goldenboy.core.loop_detection.LoopDetector`'s
  per-signature repeat counts. Only a hashed signature and the tool name
  are stored, never the raw arguments/error text that produced the hash.
- **`failures.json`** — `goldenboy.core.failure_memory.FailureMemoryStore`'s
  records: a hashed signature, a redacted cause summary, attempt count, and
  optional resolution text (also redacted).
- **`snapshots.jsonl`** — `goldenboy.core.snapshot.SnapshotManager`'s
  recorded checkpoints: a label, timestamp, and git commit/stash object
  hashes. No file contents are stored here directly — the actual content
  lives in git's own object store (`.git/`), which this file only points
  into.

Nothing else is written to disk, and no file above is meant to ever
contain an API key, prompt text, or raw provider response body — see
"Secret redaction" below for what happens if free-text passed into
`AuditEntry`/`FailureRecord` fields happens to contain something that
looks like one anyway.

### Secret redaction

`goldenboy.core.redaction.redact_secrets` is a defensive second layer, not
Golden Boy's primary safeguard (the primary safeguard is simply never
passing a secret into these fields — see "Credentials" below). It pattern-
matches common credential shapes (`sk-...`/`sk-ant-...` API keys, GitHub
tokens, AWS access key IDs, Slack tokens, `Authorization: Bearer ...`
headers, and explicit `key=value`/`key: value` assignments naming a
credential) and replaces any match with `[REDACTED]` before
`goldenboy.core.audit.AuditEntry.create()` or `goldenboy.core.
failure_memory.FailureMemoryStore.record()`/`.resolve()` write to disk.
It is pattern-based, not a secrets-scanning service — it will not catch
every possible credential shape, only recognizable ones.

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

Golden Boy parses on-disk files under `.goldenboy/` (`config.json`, `policy.json`, `router.json`,
`checkpoint.json`, `history.jsonl`, `telemetry.jsonl`, `spending.jsonl`, `loop_state.json`,
`failures.json`, `snapshots.jsonl`). All are read with plain `json.load`/`json.loads` — never `eval`,
`pickle`, or `yaml.load`. A malformed or hostile config/state file can only ever cause a typed
`GoldenBoyError` subclass (`ConfigError`/`PolicyError`/`RouterConfigError`/`CheckpointError`/
`LoopStateError`/`FailureMemoryError`) naming the problem, never a raw traceback; a malformed line in an
append-only `.jsonl` log is silently skipped and counted, never raised as a fatal error, so one corrupted
line cannot block reading the rest of a real log. None of these files can execute code, and none write
outside `.goldenboy/` (or, for `snapshot.py`, outside git's own object store — see below). Their paths are
fixed relative to the current working directory and are not built from any external or remote input, so
there is no path-traversal surface via a CLI argument today; this would need re-review if a future version
accepts a user-supplied path for any of them.

`goldenboy.core.governance.PolicyConfig` additionally compiles `denied_command_patterns`/
`approval_command_patterns` as regular expressions (`re.compile`) — a malformed pattern raises
`PolicyError` naming the bad pattern rather than propagating a raw `re.error`, and matching is
case-insensitive `search()` against caller-supplied command text, never `eval`/`exec`.

### Subprocess usage

Two modules invoke external processes, both via `subprocess.run(argv_list, ...)` with an explicit
argument list and **`shell=False`** (the default) — never a shell string, so shell-metacharacter
injection (`;`, `|`, `` ` ``, `$(...)`) is not a risk even though the inputs originate from the caller's
own CLI arguments:

- **`goldenboy.core.snapshot`** (git-based checkpoint/rollback, see `README.md`) runs `git` subcommands
  (`rev-parse`, `stash create`, `checkout`) against `repo_dir`, and runs caller-supplied verification
  commands (`goldenboy snapshot verify --check "..."`) parsed with `shlex.split` into an argv list before
  being passed to `subprocess.run` — the string is *parsed*, never executed through a shell.
- **`goldenboy.core.benchmark`** (`scripts/benchmark.py` / `goldenboy benchmark`) shells out to the
  installed `goldenboy` console-script entry point itself, purely to measure CLI cold-start latency.

Both are opt-in, explicit CLI features (you have to run `goldenboy snapshot`/`goldenboy benchmark`), not
something triggered by parsing an untrusted file.

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

# Changelog

All notable changes to this project are documented in this file, using the
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [Unreleased]

### Budget-aware, policy-governed, verifiable agent runtime (2026-09-18)

Selectively adopts autonomous-agent-runtime design concepts (policy
enforcement, budget-aware execution, model routing, checkpoints, loop
detection, failure memory, execution auditing) into Golden Boy's existing
architecture, scoped to Golden Boy's own stated purpose (controlling AI
task cost and execution behavior) — not a wholesale adoption of any other
project's feature set. See README.md's "Design Inspiration" section for
what was and wasn't adopted, and the new modules' own docstrings for the
specific reasoning behind each one.

All of the below is additive: no existing public API, CLI command, or
config default changed behavior. `goldenboy/__init__.py`'s previously
existing exports are unchanged; new ones were only added.

#### Added

- **Policy Engine** (`goldenboy/core/governance.py`, `goldenboy policy`
  CLI command): code-level, not prompt-level, enforcement of what an agent
  action is allowed to do. `PolicyEngine.evaluate()` runs four checks in a
  fixed order (permission → budget → risk → scope) and returns
  `ALLOW`/`DENY`/`REQUIRE_APPROVAL` — never a warning. Rules (denied
  tools/commands, protected file-path patterns, session/day budget caps,
  a single-action cost-approval threshold) live in `PolicyConfig`, loaded
  from `.goldenboy/policy.json` via the same defaults → file → env-var
  cascade `GoldenBoyConfig` already uses. Deliberately named/namespaced
  apart from the pre-existing `goldenboy.core.policies` module (baseline
  proceed/stop policies used by `goldenboy replay`) to avoid colliding
  with that established, unrelated concept.
- **Budget ledger** (`goldenboy/core/spending.py`, `goldenboy spend` CLI
  command): session- and day-scoped cumulative token spend tracking in
  absolute tokens, layered on top of (not replacing) `Budget`/
  `RiskEngine`'s existing per-check percentage semantics. Keeps
  `estimated_tokens` and `actual_tokens` distinct in every field and
  render path — an estimate is never displayed as if it were measured.
- **Model Router** (`goldenboy/core/router.py`, `goldenboy route` CLI
  command): maps task complexity (`DecisionEngine`'s existing
  LOW/MEDIUM/HIGH/VERY_HIGH label — reused, not reinvented) and budget
  risk (`RiskEngine`'s existing `ExecutionMode` — reused) to one of six
  provider-neutral tiers (`STOP`/`MINIMAL`/`CHEAP`/`STANDARD`/`HIGH`/
  `HIGHEST`). Budget risk can only downgrade the tier complexity alone
  would imply, never upgrade it. Ships with zero real model names or
  pricing data — mapping a tier to an actual model identifier is optional,
  caller-supplied config (`.goldenboy/router.json`); unconfigured, a
  `RoutingDecision.model_name` is `None`, not a guess.
- **Audit Log** (`goldenboy/core/audit.py`, `goldenboy audit` CLI
  command): an append-only, human-reviewable record of governance
  decisions (action, tool, policy verdict/reason, estimated/actual cost,
  result, error), distinct in scope from the pre-existing `HistoryStore`
  (which records `budget_aware_execution`'s own decisions for
  analytics/replay). `PolicyEngine` writes to it automatically when
  constructed with an `AuditStore`. `error`/`extra` free-text fields pass
  through the new `goldenboy.core.redaction.redact_secrets` first.
- **Secret redaction** (`goldenboy/core/redaction.py`): pattern-based
  best-effort masking of common credential shapes (API keys, bearer
  tokens, `key=value` assignments) in free-text fields before they're
  persisted — a defensive second layer behind "never pass a secret in".
- **Checkpoint / rollback of working-tree changes**
  (`goldenboy/core/snapshot.py`, `goldenboy snapshot` CLI command):
  git-based (no second version-control system) — `create()` records the
  current commit plus a `git stash create` object (touches nothing in the
  working tree/index/stash list), `verify()` runs caller-supplied
  typecheck/test/build commands in order, and `rollback()` restores
  tracked-file content to snapshot time via `git checkout <sha> -- .`.
  Named `snapshot`, not `checkpoint`, specifically to not collide with the
  pre-existing, unrelated `CheckpointManager` (task-plan checkpoint/resume).
  Known, documented limitation: files that were untracked at snapshot time
  are not restored/removed by rollback.
- **Loop detection** (`goldenboy/core/loop_detection.py`, `goldenboy loop`
  CLI command): persistent per-(tool, args, error)-signature repeat
  counter; `GoldenBoyConfig.loop_repeat_threshold` (new config field,
  default 3) controls when `should_stop` becomes `True`. Only a hash of
  the signature is persisted, not the raw text, matching
  `HistoryStore.TaskEvent.prompt_hash`'s existing privacy convention.
- **Failure memory** (`goldenboy/core/failure_memory.py`, `goldenboy
  failure` CLI command): a minimal record of why past tasks failed, keyed
  by a normalized (digits blanked) signature hash so near-identical
  failures accumulate one `attempt_count` instead of duplicating.
  `find_similar()` does keyword-overlap (Jaccard) matching, no embeddings
  or vector database, per the project brief's "keep it simple" directive.
- **Heartbeat** (`goldenboy/core/heartbeat.py`, `goldenboy heartbeat` CLI
  command) — **experimental**: a single, synchronous, local-file-only
  "does anything need attention" check (pending checkpoint, exhausted or
  changed budget, a loop-detection stop). Never calls an LLM or makes a
  network request, and is explicitly not a background daemon/server —
  Golden Boy still does not run one (see ROADMAP.md's non-goals); a
  caller's own scheduler invokes `check()`/`goldenboy heartbeat`
  periodically.
- `GoldenBoyConfig.loop_repeat_threshold` (new field, default `3`,
  range `[1, inf)`), following the same range-validated,
  env-var-overridable pattern as the module's existing fields.
- 189 new tests across `tests/test_governance.py`, `test_spending.py`,
  `test_router.py`, `test_audit.py`, `test_redaction.py`,
  `test_loop_detection.py`, `test_failure_memory.py`, `test_snapshot.py`,
  `test_heartbeat.py`, and `test_cli_governance.py` (186 → 375 total).

#### Changed

- `.gitignore`: added `.DS_Store`.
- `SECURITY.md`: documented the new `.goldenboy/*` files above, the
  secret-redaction layer, and corrected a since-stale claim that the
  package contained no `subprocess` calls (it did already, in
  `goldenboy/core/benchmark.py`'s CLI-startup benchmark — `snapshot.py`'s
  git/verify-command invocations are new, documented alongside it).
- `.github/workflows/ci.yml`: the build job's installed-wheel smoke check
  now also exercises every new CLI command.

#### Explicitly not done in this change (see README.md's honesty labeling)

- No wallet/USDC/x402/ERC-8004/blockchain identity/agent marketplace/
  agent-replication/self-funded-agent-economy/autonomous-trading feature
  of any kind — out of scope for Golden Boy's stated purpose, not adopted.
- No deep, automatic wiring of the Policy Engine/Audit Log into
  `AdaptiveExecutor`/`budget_aware_execution` — those two remain
  unchanged and fully backward-compatible; the new modules are
  independently composable (own CLI command, own Python API), the same
  shape `budget_aware_execution` itself already uses ("wrap your own
  callable"), rather than forcing a new mandatory pipeline through
  already-tested, already-stable code.
- No learned/ML component anywhere in the new modules (loop detection,
  failure memory, and the router are all fixed, deterministic logic) —
  same "deterministic baseline first" principle the pre-existing
  `TaskClassifier`/`GoldenBoyPolicy` already follow.

### Evidence-driven intelligence & telemetry upgrade (2026-09-17)

Closes the P0 gap flagged (but deliberately not fixed) by the 2026-09-15
architecture audit (`ARCHITECTURE_AUDIT.md` §7): `Estimator.estimate_task()`
returned essentially the same ~66.4–66.5% cost estimate for all 8 scenario
prompts in `scripts/validate_policy.py`'s budget-curve validation, because
whole-repository size dominated the formula regardless of task content.
Re-running that exact harness today, after this change, produces
5.0%–28.5% across the same 8 scenarios, correctly differentiated by task
signals instead of repo size — compare
`benchmarks/results/2026-09-17-policy-validation-BEFORE-p0-fix.md`
(a preserved snapshot reproducing the original finding, taken immediately
before this fix) against `benchmarks/results/2026-09-17-policy-validation.md`
(the same script, same machine, same day, after the fix).

#### Added

- **Context relevance** (`Estimator._estimate_relevant_context`, `goldenboy/
  core/estimator.py`): scores each candidate source file's *path* against
  keywords extracted from the task text (plus a test-association and a
  30-day recency bonus), and only that bounded, possibly-empty subset of
  files feeds the cost estimate — not the whole repository. A task whose
  wording matches nothing in the repo now reports zero relevant context
  (and a correspondingly lower `TaskEstimate.confidence`), not a
  repo-sized number. `Estimator._estimate_codebase_context` (whole-repo
  size) is unchanged and still computed, but only for transparency
  (`TaskEstimate.repository_tokens`) — it no longer feeds the total.
- **Independent task-complexity model** (`goldenboy/core/complexity.py`,
  new module): a fixed, documented keyword/clause-structure signal table
  (`architecture_keyword`, `migration_keyword`, `cross_module_keyword`,
  `api_change_keyword`, `dependency_change_keyword`,
  `test_requirement_keyword`, `refactor_keyword`, `multi_step_scope`)
  producing a `[0, 1]` heuristic score — explicitly documented as *not* a
  calibrated probability. `Estimator.estimate_task()` now scales its
  expected-output-size multiplier (1.5x–5x, previously a fixed 3x) by this
  score, and `DecisionEngine`/`TaskProfile.complexity` now reads it
  directly instead of back-computing complexity from the cost percentage
  (see `decision_engine.py`'s updated module docstring).
- **`TaskEstimate` breakdown fields**: `repository_tokens`,
  `relevant_context_tokens`, `relevant_file_count`, `prompt_tokens`,
  `estimated_output_tokens`, `verification_tokens`, `complexity_score`,
  `complexity_signals` — every term of the new
  `relevant_context + prompt + expected_output + verification` cost
  formula is individually inspectable. Defaulted for backward
  compatibility; existing `TaskEstimate(estimated_percentage=..., 
  confidence=...)` call sites are unaffected.
- **Multi-label task classification** (`TaskClassifier`): `TaskClassification.
  secondary_task_types` — other task types that also scored meaningfully
  (>= 50% of the top type's score), ordered by score, capped at 3. The
  existing single-label `task_type`/`confidence` fields are unchanged.
- **Execution telemetry contract** (`goldenboy/core/telemetry.py`, new
  module): `ExecutionTelemetry` — a self-contained record of what an
  external agent actually observed after acting on a `goldenboy analyze`
  decision (echoed `estimated_cost_percentage` + real
  `actual_total_tokens`/`duration_seconds`/`tests_run`/`tests_passed`/
  `files_touched`/etc., all optional except `final_outcome`), plus a
  first-class `verification_status` (`VERIFIED`/`PARTIALLY_VERIFIED`/
  `UNVERIFIED`/`FAILED`) distinguishing a *claimed* outcome from a
  *verified* one. Persisted via `TelemetryStore`
  (`.goldenboy/telemetry.jsonl`, same append-only JSONL convention as
  `HistoryStore`). New CLI commands: `goldenboy report` (record one
  telemetry event, via flags or `--json-file`) and `goldenboy calibrate`
  (MAE/RMSE/median-absolute-error/bias/over-under-estimation-rate,
  overall and per task type, from real recorded telemetry — reports N/A
  below 10 samples, same convention as `goldenboy replay`). See
  `goldenboy/core/calibration.py` and `skills/goldenboy/SKILL.md`'s new
  "Closing the loop" section for the external-agent integration contract.
- `schemas/decision.schema.json` — formal JSON Schema for the Golden Boy
  Protocol, plus cross-language compatibility tests
  (`tests/test_protocol_schema.py`, `sdk/typescript/test/schema.test.ts`).
- `scripts/benchmark_scaling.py` — the previously-Planned "large synthetic
  repository" benchmark from `ROADMAP.md`, plus prompt-size and
  history-log-size scaling. Results in `benchmarks/results/`.
- `scripts/validate_policy.py` — realistic task/budget-curve validation of
  `DecisionEngine` and every baseline in `goldenboy.core.policies` against
  identical inputs, plus real (not fabricated) `goldenboy validate`/
  `goldenboy replay` output. Results in `benchmarks/results/`.

#### Changed

- `goldenboy.protocol.PROTOCOL_VERSION`: `1.0.0` → `1.1.0` (additive:
  `TaskProfile.complexity_signals`, `TaskProfile.secondary_task_types`;
  `TaskProfile.complexity`'s *value* now comes from the new independent
  complexity model rather than being back-computed from cost — same field
  name/type/range, different computation. Old readers using
  `.get(field, default)` — as both `protocol.py` and the TypeScript SDK's
  `validate.ts` already do — degrade gracefully on the two new fields).
  `sdk/typescript/src/types.ts` and `schemas/decision.schema.json` updated
  to match.
- `Estimator.estimate_task()` latency on this repository: ~9.3ms (2026-09-13)
  → ~41.4ms (2026-09-17, measured) — a real, expected increase (two
  file-tree walks instead of one, plus complexity scoring), not a
  regression to hide. See `BENCHMARKS.md`'s 2026-09-17 entry for the full
  before/after and why it's still imperceptible in practice.

#### Performance fix (caught and fixed within this same unreleased change, before any release)

- Bounded how much of the task text `goldenboy.core.complexity.
  estimate_task_complexity` and `Estimator._extract_keywords` regex-scan
  (`_MAX_SCAN_CHARS` / `_MAX_TASK_TEXT_SCAN_CHARS` = 20,000 characters).
  Without this, a pathologically large prompt (~25M characters — not a
  realistic task description, but Golden Boy must not hang on one) took
  ~9.8s in `estimate_task()`, almost entirely in repeated full-text regex
  scans; measured down to ~0.56s (mostly legitimate tiktoken encoding of
  the same prompt) after bounding. Regression test:
  `tests/test_complexity.py::test_pathologically_large_prompt_does_not_hang`.

## [1.1.0] - 2026-09-14

Production-intelligence upgrade: a stable cross-language protocol, task
understanding, local history/analytics, a genuine backtest framework, a
much richer CLI, and a TypeScript SDK — all additive; every existing
public API, CLI command's default behavior, and test from 1.0.0 keeps
working unchanged.

### Added

- **Golden Boy Protocol** (`goldenboy/protocol.py`): a versioned,
  language-neutral `GoldenBoyDecision` schema (`TaskProfile`/
  `UsageSnapshot`/`RiskAssessment` → action/confidence/reason), strict
  `from_dict` validation (`ProtocolError`), JSON round-trippable.
  Documented in `docs/PROTOCOL.md`.
- **Task intelligence**: `TaskType` (13-value classification vocabulary),
  `TaskClassifier` (deterministic, keyword-weighted, heuristic-confidence
  — explicitly not ML, see its module docstring for why), and
  `DecisionEngine` (combines `RiskEngine` + `TaskClassifier` + `Estimator`
  into one explained decision, with a conservative policy for
  UNKNOWN-confidence budgets applied at this new layer only —
  `RiskEngine`'s own tested UNKNOWN handling is unchanged).
- **Local history & analytics**: `HistoryStore`/`TaskEvent`
  (`.goldenboy/history.jsonl`, gitignored like the checkpoint file, wired
  into `budget_aware_execution`, never stores raw task text — only length
  + a truncated hash), `goldenboy.analytics.data_quality` (a real Dataset
  Quality report), and `goldenboy.analytics.engine` (cost/completion/
  failure/deferral-rate aggregates). Both report `NO_DATA`/`None` honestly
  on a fresh install rather than a fabricated baseline.
- **Baseline policies & replay/backtesting**: `goldenboy.core.policies`
  (two fixed-threshold baselines, complexity-only, usage-only, and
  `GoldenBoyPolicy` wrapping the real `RiskEngine`) and
  `goldenboy.replay.engine` (`run_backtest` — precision/recall/accuracy/
  premature-stop-rate/unnecessary-continuation-rate; `walk_forward_folds`
  — chronological, leakage-safe splitting). Reports `N/A` below 10 events;
  there is no real historical dataset shipped or fabricated — see
  `docs/DATASETS.md` for the dataset landscape review this design is
  based on.
- **CLI**: `goldenboy analyze` (the full `DecisionEngine` recommendation),
  `goldenboy validate` (config + checkpoint + data-quality, exits 1 on a
  real problem), `goldenboy replay` (`--dataset` for an exported/shared
  history file), `goldenboy benchmark`, `goldenboy export`
  (config+checkpoint+history as one reproducible JSON document); `--json`
  added to `status`/`doctor` too. `goldenboy/core/benchmark.py` extracted
  so `scripts/benchmark.py` and `goldenboy benchmark` share one
  implementation instead of two copies.
- **TypeScript SDK** (`sdk/typescript/`): `GoldenBoyClient` spawns the
  real `goldenboy` CLI and parses its `--json` output through a
  TypeScript mirror of the same protocol validation — no reimplemented
  decision logic. Zero runtime dependencies; tests run on Node's built-in
  test runner and include real (non-mocked) integration coverage against
  the actual installed CLI.
- `docs/PROTOCOL.md`, `docs/DATASETS.md`, `docs/LANGUAGE_STRATEGY.md`.
- CI: a `sdk-typescript` job (installs the real Python package, then
  builds/tests the SDK against it); the build job's wheel-install smoke
  test now exercises every new command, plus a benchmark-sanity step
  (estimator determinism + non-negative latency — a correctness check,
  not a performance gate).

### Fixed

- `goldenboy validate`'s checkpoint line used to double its own "OK —"
  prefix (`Checkpoint: OK — OK — task ...`) because `CheckpointManager`'s
  already-prefixed success string was wrapped in a second one — caught by
  live smoke-testing, not a pre-existing test; now covered by a
  regression test.
- `SECURITY.md`'s "Supported versions" section still said "pre-1.0
  (0.1.x)" after the 1.0.0 release; corrected, and extended to describe
  `history.jsonl` (what it stores, that it never contains raw prompt text).

### Validation

- 186 Python tests passing (up from 88), 95% line coverage (`pytest
  --cov`); 14 TypeScript tests passing (`npm test`, real CLI integration
  included). Ruff and mypy clean.
- Verified live against a clean-room wheel install with zero optional
  extras: every new CLI command, `--help`, and the core-only
  (`pip list` showing only `goldenboy`) install story all confirmed
  working end-to-end, not merely unit-tested in isolation.

## [1.0.0] - 2026-09-13

First stable release.

### Added
- `GoldenBoyConfig`: a single, validated source for previously
  hardcoded/scattered thresholds (`safety_margin`, `caution_ratio`,
  `base_cost_per_unit`, `max_budget_tokens`, `stale_after_seconds`),
  overridable via `.goldenboy/config.json` or `GOLDENBOY_*` env vars.
  Out-of-range values raise `ConfigError` rather than being silently
  accepted.
- `Budget.source` / `Budget.confidence` (`UsageConfidence`:
  EXACT/ESTIMATED/STALE/UNKNOWN). `AnthropicAdapter`/`OpenAIAdapter` now
  track their last successful refresh (via an injectable, `time.monotonic`
  clock) and report `STALE` once a reading is older than
  `stale_after_seconds`; a failed refresh does not reset that clock.
  `RiskEngine.assess()` reads this: a verdict that would otherwise be SAFE
  is downgraded to CAUTION when confidence is STALE (LIMITED/CRITICAL are
  hard limits, unaffected; the pre-existing UNKNOWN default is left alone).
- `AdaptiveExecutor.assess(plan)`: one decision path shared by
  `AdaptiveExecutor.execute()` and `integration.budget_aware_execution`,
  removing what used to be duplicated budget/estimate/mode logic.
- Checkpoints now record `created_at`, a `budget_snapshot`, a
  human-readable `next_recommended_action`, and a schema `version` (an
  incompatible future version raises `CheckpointError` cleanly instead of
  misreading fields).
- `goldenboy/core/errors.py`: `GoldenBoyError` / `ConfigError` /
  `CheckpointError`, caught at the CLI boundary and printed as a one-line
  `error: ...` message (exit 1) instead of a raw traceback.
- `goldenboy/__init__.py`: a small, deliberate public API (`GoldenBoyConfig`,
  `Budget`, `UsageConfidence`, `ExecutionMode`, `RiskEngine`, `Estimator`,
  `Priority`, `ExecutionUnit`, `AdaptiveExecutor`, `budget_aware_execution`,
  `ProviderAdapter`, `MockProvider`, `CheckpointManager`, error types) —
  previously empty. Provider-specific adapters are deliberately excluded,
  so `import goldenboy` never requires the `anthropic`/`openai` extras.
- `goldenboy doctor`: Python version, optional-dependency status (and
  whether `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are configured — never
  their value), config validity, and checkpoint state.
- Optional dependency groups (`goldenboy[anthropic]`, `[openai]`,
  `[tiktoken]`) — the core package, CLI, and `skills/goldenboy/SKILL.md`
  workflow require none of them.
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `.env.example`,
  `scripts/benchmark.py` + `BENCHMARKS.md` (real, dated, methodology-labeled
  latency numbers), and a CI workflow (lint, type check, tests + coverage,
  build + wheel install, `pip-audit`) across Python 3.9-3.13.
- 80 new tests since the initial implementation (8 → 88): estimator
  correctness, config validation boundaries, risk-threshold boundaries,
  checkpoint corruption/versioning, adapter usage-confidence and STALE
  lifecycle (deterministic, via a fake clock — no real sleeping), the
  public API surface, and CLI end-to-end behavior including every error
  path below.

### Fixed
- `Estimator` no longer walks into `venv/`, `node_modules/`, `.git/`, or
  other dependency/build directories when scanning repo context — this
  previously inflated the token count 20x+ from an installed virtualenv
  alone, clamping trivial tasks to a false 100% estimated cost. Its
  no-tiktoken fallback also no longer uses a pure word-count heuristic,
  which could return identical estimates for different-content prompts of
  equal word count.
- `goldenboy plan`/`run` no longer ignore the task text passed to them —
  `plan` computes its cost estimate from the real prompt, and the CLI's
  fixed example plan is labeled illustrative rather than implied to be
  derived from the task.
- `AnthropicAdapter`/`OpenAIAdapter` no longer send a throwaway chat
  completion and report success as if a described coding task had been
  performed. `ProviderAdapter.execute_unit` is optional (raises
  `NotImplementedError` with guidance toward `budget_aware_execution`);
  the real adapters no longer implement it.
- A corrupted `.goldenboy/checkpoint.json` or malformed
  `.goldenboy/config.json` used to crash every CLI command with a raw
  traceback; an empty/whitespace-only task was silently accepted. All now
  produce a clean, specific error and exit 1.
- A cross-version mypy type-narrowing failure in `GoldenBoyConfig.load()`
  — passed locally under mypy 2.3.1 but failed CI's Python 3.9 job, which
  resolves mypy 1.19.1. Found by GitHub Actions, not local testing; fixed
  with an explicit `isinstance` guard and verified clean under both
  versions.

### Changed
- `skills/goldenboy/SKILL.md` documents all four execution modes
  (previously omitted CAUTION) and the concrete `<total_tokens>`
  system-reminder signal Claude Code exposes, plus an explicit
  responsibility-boundary statement (Golden Boy decides how aggressively
  to proceed; the calling agent remains responsible for the task itself).
- README rewritten around a single value proposition, with real, current
  numbers in a dedicated Validation section — no numbers are asserted that
  weren't actually measured on this release.
- `run_tests.py` now delegates to `pytest` instead of hand-listing test
  functions.

### Validation
- 88 tests passing, 93% line coverage (`pytest --cov`)
- Ruff clean; mypy clean under both 1.19.1 and 2.3.1
- `pip-audit`: 0 known vulnerabilities
- Python 3.9, 3.10, 3.11, 3.12, 3.13 — all passing on GitHub Actions
- Wheel and sdist built, `twine check` passed, both installed into
  independent fresh virtual environments
- Core install (`pip install goldenboy`) verified to pull zero
  third-party runtime dependencies

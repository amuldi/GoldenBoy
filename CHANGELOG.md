# Changelog

All notable changes to this project are documented in this file, using the
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [Unreleased]

### Fixed (found by real GitHub Actions, not local testing)
- `GoldenBoyConfig.load()`'s env-var casting (`fld.type in (int, float)`)
  passed mypy locally (2.3.1) but failed CI's Python 3.9 job, which pip
  resolved to mypy 1.19.1 — an older version that can't narrow
  `dataclasses.Field.type` (typed as `type | str`) through a plain `in`
  check. Reproduced locally by installing mypy==1.19.1 before fixing.
  Fixed with an explicit `isinstance(fld.type, type)` guard, which every
  mypy version narrows the same way; verified clean under both 1.19.1 and
  2.3.1 locally.

### Added (this pass)
- `UsageConfidence.STALE` is now actually set, not just defined.
  `AnthropicAdapter`/`OpenAIAdapter` track when they were last
  successfully refreshed (via an injectable clock, `time.monotonic` by
  default) and report `STALE` instead of `ESTIMATED` once that reading is
  older than the new `GoldenBoyConfig.stale_after_seconds` (default 300s).
  A failed `refresh_usage()` call does not reset the staleness clock.
- `RiskEngine.assess()` now reads `Budget.confidence`: a verdict that
  would otherwise be SAFE is reported as CAUTION when confidence is
  STALE. LIMITED/CRITICAL are unaffected (they're hard limits regardless
  of confidence), and the pre-existing UNKNOWN default is deliberately
  left alone so no caller that doesn't set confidence explicitly changes
  behavior.
- `goldenboy doctor` now reports whether `ANTHROPIC_API_KEY`/
  `OPENAI_API_KEY` are configured (present/absent only — verified live
  that the actual key value never appears in its output).
- Product decision, recorded: `plan`/`run`'s illustrative-example-plan
  approach is kept as-is for the CLI (analyzed against building real task
  decomposition; see `ROADMAP.md` "Explicit non-goals" for the reasoning).
  No CLI or output changes resulted beyond what was already shipped.
- 12 new tests: STALE lifecycle for both adapters (aging, refresh
  restoring freshness, failed refresh not resetting the clock — all via a
  deterministic fake clock, no real sleeping), `RiskEngine`'s
  STALE-forces-CAUTION rule (plus that it doesn't touch LIMITED/CRITICAL
  or the pre-existing UNKNOWN default), `stale_after_seconds` config
  validation, and `doctor`'s API-key-status reporting.

### Fixed
- `Estimator._estimate_codebase_context` no longer walks into `venv/`,
  `node_modules/`, `.git/`, and other dependency/build directories. Previously
  this could inflate the "codebase context" token count by 20x+ from an
  installed virtualenv alone, clamping trivial tasks (e.g. "fix a typo") to a
  false 100% estimated cost.
- `goldenboy plan <task>` and `goldenboy run <task>` no longer ignore the
  task text you pass in. `plan` now calls `Estimator.estimate_task()` on the
  real prompt; both commands print the actual task string, and the CLI's
  fixed example plan is now clearly labeled illustrative rather than implied
  to be derived from your task.
- `AnthropicAdapter`/`OpenAIAdapter.execute_unit` no longer sends a
  throwaway chat completion and reports success as if the described coding
  task had been performed. `ProviderAdapter.execute_unit` is now optional
  (raises `NotImplementedError` by default with guidance toward
  `budget_aware_execution`); the two real adapters no longer implement it.
- A corrupted `.goldenboy/checkpoint.json` or malformed `.goldenboy/config.json`
  used to crash any CLI command with a raw traceback. Both now raise
  `CheckpointError`/`ConfigError`, caught at the CLI boundary and printed as
  a one-line `error: ...` message (exit code 1).
- Out-of-range config values (e.g. `caution_ratio` outside `[0, 1]`, a
  negative `safety_margin`) were silently accepted, including silently
  breaking the CAUTION tier entirely. Now validated in
  `GoldenBoyConfig.__post_init__` and rejected with a specific message.
- `goldenboy plan`/`run` silently accepted an empty or whitespace-only task
  and produced a plausible-looking estimate; now rejected with a clear
  usage error.
- `tests/test_executor.py::test_executor_critical_mode` was misnamed: the
  scenario it exercised actually assessed **LIMITED**, not CRITICAL
  (verified directly via `RiskEngine.assess()`) — the assertions happened
  to still pass either way, but the name/comments were wrong. Renamed the
  original to `test_executor_limited_mode_with_mid_execution_exhaustion`
  and added a real CRITICAL-mode test (budget already at/below the safety
  margin from the first assessment).
- `GoldenBoyConfig.load()` reused a loop variable (`f`) for both a file
  handle and a `dataclasses.fields()` iterator in the same method —
  harmless at runtime, confusing to read, and flagged by mypy. Renamed.
- Two latent type-safety gaps in `AnthropicAdapter`/`OpenAIAdapter
  .get_available_budget()`: the "not yet refreshed" guard checked only one
  of two fields that are always set together. Not a reachable bug today,
  but made the invariant explicit rather than implicit (caught by mypy).

### Added
- `goldenboy/core/config.py`: a single `GoldenBoyConfig` for previously
  hardcoded/scattered thresholds (safety margin, SAFE/CAUTION ratio,
  per-unit cost fallback, token-to-percentage normalization constant),
  overridable via `.goldenboy/config.json` or `GOLDENBOY_*` env vars.
- `Budget.source` and `Budget.confidence` (`UsageConfidence`:
  EXACT/ESTIMATED/STALE/UNKNOWN). Mock usage is EXACT; rate-limit-header
  usage is ESTIMATED once refreshed, UNKNOWN before the first refresh —
  never presented as an exact session budget.
- `AnthropicAdapter.refresh_usage()` / `OpenAIAdapter.refresh_usage()`: an
  explicit, honestly-named method for the one legitimate reason to make a
  minimal probe call (reading rate-limit headers), separated from the
  removed fake "execution" path.
- `AdaptiveExecutor.assess(plan)`: the shared assess-then-decide path now
  used by both `AdaptiveExecutor.execute()` and
  `integration.budget_aware_execution`, removing the duplicated
  budget/estimate/mode logic that previously lived in both places.
- Checkpoint files now include `created_at`, a `budget_snapshot`, and a
  human-readable `next_recommended_action` summary (shown by `goldenboy
  status`), instead of just the raw unit list.
- `goldenboy` CLI gained `-v`/`--verbose` to surface internal INFO/WARNING
  logs; library internals (`executor.py`, `integration.py`) now use
  `logging` instead of unconditional `print()`.
- Optional dependency groups: `pip install goldenboy[anthropic]` /
  `[openai]` / `[tiktoken]`. The core package, CLI demo, and
  `skills/goldenboy/SKILL.md` workflow no longer require either LLM SDK.
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `.env.example`,
  and a CI workflow (lint + test + build) — previously missing despite the
  README linking to `LICENSE`.
- 21 new tests: estimator context-scan correctness, config precedence,
  risk-threshold boundaries, adapter usage-confidence labeling, and the
  integration decorator's execution/defer paths.
- `goldenboy/core/errors.py`: `GoldenBoyError` / `ConfigError` /
  `CheckpointError`, caught at the CLI boundary instead of leaking raw
  tracebacks for normal user mistakes.
- Checkpoint schema versioning (`CHECKPOINT_SCHEMA_VERSION`) — a checkpoint
  from an incompatible future version now raises a clear `CheckpointError`
  instead of silently misreading fields that changed meaning.
- `goldenboy/__init__.py` now exports a small, deliberate public API
  (`GoldenBoyConfig`, `Budget`, `UsageConfidence`, `ExecutionMode`,
  `RiskEngine`, `Estimator`, `TaskEstimate`, `Priority`, `ExecutionUnit`,
  `AdaptiveExecutor`, `budget_aware_execution`, `ProviderAdapter`,
  `MockProvider`, `CheckpointManager`, and the error types) — previously
  empty. Provider-specific adapters stay out of it deliberately, so
  `import goldenboy` never requires the `anthropic`/`openai` extras
  (verified in a clean venv with neither installed).
- `goldenboy doctor`: reports Python version, which optional dependencies
  are installed, whether config loads without error, and current
  checkpoint state — real, checked facts, no invented health score.
- mypy adopted (`[tool.mypy]` in `pyproject.toml`) — clean across the whole
  package, including in an environment without the optional extras.
- `scripts/benchmark.py` + `BENCHMARKS.md`: real, reproducible latency
  measurements (estimator, risk engine, CLI cold start), explicitly
  labeled with methodology and what's *not* yet measured (provider-API
  latency, large-repo behavior).
- Packaging metadata: `license`, `classifiers`, and `project.urls`
  (Homepage/Repository/Issues/Changelog) pointing at the real `origin`
  remote.
- CI gained a type-check step, a coverage report (informational, no
  enforced threshold), and a `pip-audit` dependency-vulnerability job.
- ~20 further tests: CLI-level end-to-end coverage (task differentiation,
  corrupted checkpoint/config, empty task, `doctor`, a full `run`→`resume`
  round trip), checkpoint corruption/versioning, config validation
  boundaries, the public API surface, and adapter refresh-failure paths.

### Changed
- `skills/goldenboy/SKILL.md` now documents all four execution modes
  (previously omitted CAUTION, inconsistent with the code/README) and
  names the concrete `<total_tokens>` system-reminder signal Claude Code
  exposes, instead of a vague "your internal context window" reference.
- `run_tests.py` now delegates to `pytest` instead of hand-listing test
  functions, which used to silently stop covering new test files.
- README's hero image now uses an absolute GitHub URL instead of a
  relative path — the relative path would have rendered broken if this
  package were ever published (PyPI doesn't ship `assets/`). Found by
  inspecting the built wheel's actual contents, not by inspection alone.
- README gained Quick Start, Python integration, Configuration, Safety
  model, Roadmap, and Contributing sections; hero copy's unverified
  "Guarantees results... 100% recoverable... Measured on..." language
  (which by this point directly contradicted the Limitations section) was
  replaced with accurate, still-confident language.

## [0.1.0] - Prior to this changelog

Initial implementation: `Budget`/`RiskEngine`/`AdaptiveExecutor` core,
`MockProvider`, priority/checkpoint model, CLI (`status`/`plan`/`run`/`resume`),
`budget_aware_execution` decorator, OpenAI/Anthropic rate-limit-header
adapters, tiktoken-based estimator, and the `skills/goldenboy/SKILL.md`
prompt-level integration.

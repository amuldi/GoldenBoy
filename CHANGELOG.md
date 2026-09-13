# Changelog

All notable changes to this project are documented in this file, using the
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

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

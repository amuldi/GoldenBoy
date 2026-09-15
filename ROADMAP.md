# Roadmap

Status definitions: **Done** (implemented and covered by tests) · **In
Progress** · **Planned** (agreed direction, not started) · **Research**
(idea, not yet validated as worth building).

## Core

| Item | Status |
|---|---|
| Budget/Risk/Executor core (SAFE/CAUTION/LIMITED/CRITICAL) | Done |
| Checkpoint save/resume with budget snapshot + next-action hint | Done |
| Checkpoint schema versioning (reject incompatible future versions cleanly) | Done |
| Centralized, overridable policy config (`GoldenBoyConfig`) | Done |
| Config/checkpoint validation (malformed file, out-of-range value, missing field -> clear error, not a traceback) | Done |
| Usage confidence/source labeling (EXACT/ESTIMATED/STALE/UNKNOWN) | Done |
| `STALE` confidence actually detected (adapter-tracked refresh age vs. `stale_after_seconds`, injectable clock for tests) and acted on (`RiskEngine` won't report SAFE on STALE data) | Done |
| Task decomposition: turning a natural-language task into real `ExecutionUnit`s | Explicit non-goal for the `plan`/`run` CLI commands — analyzed and decided against (see below); belongs in the calling agent (via SKILL.md-style prompting), not in Golden Boy itself |

## Agent integrations

| Item | Status |
|---|---|
| `budget_aware_execution` decorator (agent-agnostic, wraps any callable) | Done |
| `MockProvider` (demos, tests) | Done |
| `AnthropicAdapter` / `OpenAIAdapter` (rate-limit-header usage reporting) | Done |
| Claude Code: `skills/goldenboy/SKILL.md` prompt-level integration | Done |
| `goldenboy doctor` (Python version, optional deps + API-key-configured status, config, checkpoint diagnostics) | Done |
| Golden Boy Protocol (`goldenboy/protocol.py`): versioned, language-neutral `GoldenBoyDecision` schema | Done — documented in `docs/PROTOCOL.md` |
| TypeScript SDK (`sdk/typescript/`): thin client over the CLI's `--json` output, real integration-tested against the actual CLI | Done |
| Codex integration | Research — no adapter exists yet; would need a real, documented usage signal from Codex before building one (see "No fake support" principle) |

## Task intelligence

| Item | Status |
|---|---|
| `TaskType` classification vocabulary (13 values) | Done |
| `TaskClassifier`: deterministic, keyword-weighted classification with a heuristic (not calibrated-probability) confidence score | Done |
| `DecisionEngine`: combines `RiskEngine` + `TaskClassifier` + `Estimator` into one explained `GoldenBoyDecision` (action/confidence/reason), plus a conservative policy for UNKNOWN-confidence budgets applied at this layer only | Done |
| `goldenboy analyze` CLI command (text + `--json`) | Done |
| Replacing the keyword classifier with a learned model | Research — explicitly gated on real, labeled outcome data existing first (see "Data & learning" below and `goldenboy/core/task_classifier.py`'s module docstring); no such data exists yet |

## Data & learning

| Item | Status |
|---|---|
| `HistoryStore`/`TaskEvent`: local, append-only event log (`.goldenboy/history.jsonl`), wired into `budget_aware_execution`, never stores raw task text | Done |
| `goldenboy.analytics.data_quality`: real Dataset Quality report (rows, corrupted/duplicate/invalid-value ratios, status) over the local log | Done |
| `goldenboy.analytics.engine`: cost/completion/failure/deferral-rate aggregates over the local log | Done |
| `goldenboy validate` / `goldenboy export` CLI commands | Done |
| Baseline policies (`goldenboy.core.policies`: fixed-threshold ×2, complexity-only, usage-only, `GoldenBoyPolicy`) | Done |
| `goldenboy.replay.engine`: backtest (precision/recall/accuracy/premature-stop/unnecessary-continuation) + `walk_forward_folds` leakage-safe chronological splitting + `goldenboy replay` CLI command | Done — infrastructure only; reports `N/A` below 10 events, and there is no real historical dataset behind it yet (a fresh install starts at 0 events) |
| A real, populated backtest result (not `N/A`) | Blocked on real usage data accumulating via `HistoryStore` — cannot be produced honestly today; see `docs/DATASETS.md` for why no external dataset substitutes for this |
| A learned (non-fixed-threshold) policy in `goldenboy.core.policies` | Research — same gate as the task classifier above: needs real labeled outcome data first, per "start with a deterministic baseline, only then consider ML" |
| Dataset/research landscape review (SWE-bench, HumanEval, LiveCodeBench, RepoBench, published token-consumption research) | Done — `docs/DATASETS.md`; none integrated (see "why none of these" in that doc) |

## Reliability & DX

| Item | Status |
|---|---|
| CI: lint (ruff) + type check (mypy) + unit tests + coverage report + package build + dependency audit (pip-audit) | Done |
| Coverage enforced as a hard threshold | Explicit non-goal for now — reported, not gated; see below |
| Public API (`goldenboy/__init__.py`) | Done |
| Benchmark harness (`goldenboy/core/benchmark.py`, shared by `scripts/benchmark.py` and `goldenboy benchmark`) with real, dated results (`BENCHMARKS.md`) | Done for what's locally measurable (estimator/risk/CLI-startup latency) |
| CI benchmark-sanity check (estimator determinism + non-negative latency, not a performance gate) | Done |
| Benchmarking real provider-adapter latency (`refresh_usage()`) | Research — would mostly measure network/API conditions, not Golden Boy itself; revisit if that distinction turns out to matter in practice |
| Benchmarking behavior against a deliberately large synthetic repository | Done (2026-09-15) — `scripts/benchmark_scaling.py` / `benchmarks/results/2026-09-15-scaling.md`. Confirms `_MAX_SCAN_FILES=200` actually bounds latency at scale (48ms at 200 files vs. 51.6ms at 5,000). |
| Split `cli.py` into a `cli/` package | Reassessed, not a non-goal anymore — `cli.py` was ~260 lines when that reasoning was written; it's ~570 lines and 10 subcommands now. Reclassified **Planned**: worth doing once one more command is added, but deferred this cycle since a pure reorganization carries real regression risk against `cli.py`'s extensive CLI test coverage for no behavior change. |
| Language strategy review (why Python, why TypeScript where it is, why not Rust yet) | Done — `docs/LANGUAGE_STRATEGY.md`, re-confirmed with fresh benchmarks 2026-09-15 — see `ARCHITECTURE_AUDIT.md` |
| Golden Boy Protocol formalized as JSON Schema (`schemas/decision.schema.json`) + cross-language compatibility tests | Done (2026-09-15) — `tests/test_protocol_schema.py` (Python), `sdk/typescript/test/schema.test.ts` (TypeScript); fails if either implementation's required fields or enums drift from the schema |
| `HistoryStore.load_events()` has no size cap (unlike `Estimator`'s file-walk) | Planned — not a problem at today's realistic single-user scale (measured: 1.46s at a 100MB/214K-event log, see `benchmarks/results/2026-09-15-scaling.md`), but worth capping or streaming before it is one. See `ARCHITECTURE_AUDIT.md` §8. |
| `Estimator.estimate_task()`'s cost estimate is dominated by repo-context size, not prompt complexity, once the repo is moderately sized | Research — real finding, not fixed here (would change every existing estimate); see `ARCHITECTURE_AUDIT.md` §7 and `benchmarks/results/2026-09-15-policy-validation.md` |
| CI matrix is Ubuntu-only | Planned — the CLI/SDK subprocess-spawning contract is used cross-platform in practice; macOS/Windows aren't currently verified in CI. See `ARCHITECTURE_AUDIT.md` §8. |

## Explicit non-goals (for now)

- Real task decomposition in `plan`/`run` (turning task text into
  concrete `ExecutionUnit`s). Analyzed explicitly: the only real
  estimate they currently produce (task cost, from prompt + repo size) is
  already accurate and clearly labeled as such; the unit breakdown is
  explicitly labeled illustrative in both the CLI output and this README.
  Building real decomposition would require an LLM/provider dependency in
  the core path — which the "zero third-party runtime dependency" core
  install and "budget control, not task planning" scope both argue
  against — for a capability the SKILL.md prompt-level integration
  already covers at the right layer (the calling agent's own reasoning).
- Becoming a general coding assistant, chatbot, or LLM wrapper.
- Executing coding work itself outside of `MockProvider` demos — real work
  always runs through the caller's own function via
  `budget_aware_execution`.
- Fabricated benchmark numbers or "supports X" claims ahead of a working,
  tested integration.
- A hard coverage-percentage gate in CI — coverage is reported (currently
  ~95% measured via `pytest --cov`, see the engineering report in project
  history for the exact run) so regressions are visible, but chasing a
  number is not a goal in itself.
- A database, a web dashboard, or an HTTP server anywhere in this project.
  `HistoryStore` is a local JSONL file; the Golden Boy Protocol is
  transported over CLI stdout and a spawned child process
  (`sdk/typescript`), not a socket. None of these has a demonstrated need
  today — see `docs/PROTOCOL.md`'s "Why no server."
- A learned (ML) model anywhere in `goldenboy.core.task_classifier` or
  `goldenboy.core.policies` ahead of real, labeled historical data.
  `TaskClassifier` is deterministic/keyword-based and `GoldenBoyPolicy`
  wraps the existing, tested `RiskEngine` — both explicitly documented as
  the correct first step, not a placeholder for "real AI" pending unlocking.
- Rewriting any part of the core in Rust ahead of a measured bottleneck —
  see `docs/LANGUAGE_STRATEGY.md`, re-confirmed by a fresh polyglot-
  feasibility audit on 2026-09-15 (`ARCHITECTURE_AUDIT.md`) including new
  large-scale benchmarks that didn't exist when `LANGUAGE_STRATEGY.md` was
  first written.
- A second, independent CLI implementation (TypeScript or otherwise) that
  reimplements `Estimator`/`TaskClassifier`/`RiskEngine`/`DecisionEngine`
  rather than talking to the real Python CLI — evaluated and rejected in
  `ARCHITECTURE_AUDIT.md` §4/§9; `sdk/typescript` stays a thin client.

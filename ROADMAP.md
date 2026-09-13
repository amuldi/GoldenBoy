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
| Codex integration | Research — no adapter exists yet; would need a real, documented usage signal from Codex before building one (see "No fake support" principle) |
| `goldenboy history` (past checkpoints, mode transitions over time) | Research — needs real persisted history first; nothing to show yet, and it's a materially bigger feature (a history store) than the diagnostics `doctor` provides today |

## Reliability & DX

| Item | Status |
|---|---|
| CI: lint (ruff) + type check (mypy) + unit tests + coverage report + package build + dependency audit (pip-audit) | Done |
| Coverage enforced as a hard threshold | Explicit non-goal for now — reported, not gated; see below |
| Public API (`goldenboy/__init__.py`) | Done |
| Benchmark harness (`scripts/benchmark.py`) with real, dated results (`BENCHMARKS.md`) | Done for what's locally measurable (estimator/risk/CLI-startup latency) |
| Benchmarking real provider-adapter latency (`refresh_usage()`) | Research — would mostly measure network/API conditions, not Golden Boy itself; revisit if that distinction turns out to matter in practice |
| Benchmarking behavior against a deliberately large synthetic repository | Planned — the `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` caps in `estimator.py` exist for this, but the caps themselves are untested at scale |
| Split `cli.py`/`integration.py` into `cli/`/`integration/` packages | Explicit non-goal for now — both are single, cohesive files (~260 and ~60 lines) with no natural internal seam; splitting them would be churn without a concrete benefit. Revisit only if either genuinely outgrows one file. |

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
  ~93% measured via `pytest --cov`, see the engineering report in project
  history for the exact run) so regressions are visible, but chasing a
  number is not a goal in itself.
- Restructuring the repository into `goldenboy/{cli,integration}/` package
  directories to match a generic template, absent an actual reason (see
  Reliability & DX above).

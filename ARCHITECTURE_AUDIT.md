# Architecture Audit — Polyglot Feasibility Review (2026-09-15)

This audit was produced for a specific question: should Golden Boy expand
from Python into a Python + TypeScript + Rust polyglot architecture, and if
so, where? It is based on reading the actual repository, running the actual
test suite, and running (and in one case writing, then running) real
benchmarks on this machine — not on assumptions about what a project like
this "should" need. Every number in this document was measured while
writing it; see `benchmarks/results/` for the raw output.

**Bottom line up front:** most of what a polyglot upgrade would introduce
already exists, in the shape the brief itself asks for (a thin TypeScript
client over a stable protocol, never a second implementation), and the
project's own `docs/LANGUAGE_STRATEGY.md` / `ROADMAP.md` already reached —
and, as of this audit, re-confirmed with fresh measurements — the
conclusion that Rust is not justified today. This audit does not overturn
that conclusion; it re-tests it and extends it into the one place it was
previously untested (behavior at scale), plus surfaces one real,
previously-unmeasured accuracy finding unrelated to language choice at all
(§7).

## 1. Current structure

```
goldenboy/
├── __init__.py            public API surface
├── cli.py                 argparse CLI: status/plan/run/doctor/analyze/
│                           validate/replay/export/benchmark, --json on most
├── protocol.py             the Golden Boy Protocol (GoldenBoyDecision, versioned)
├── integration.py          budget_aware_execution decorator
├── adapters/               ProviderAdapter, MockProvider, Anthropic/OpenAI adapters
├── core/
│   ├── budget.py            Budget, UsageConfidence
│   ├── risk.py              RiskEngine -> ExecutionMode (SAFE/CAUTION/LIMITED/CRITICAL)
│   ├── estimator.py         Estimator: prompt + repo-context -> cost estimate
│   ├── task_classifier.py   deterministic keyword classifier -> TaskType
│   ├── decision_engine.py   combines the above into one GoldenBoyDecision
│   ├── policies.py          baseline policies + GoldenBoyPolicy, for replay
│   ├── config.py            GoldenBoyConfig (env/file/default cascade)
│   ├── checkpoint.py, history.py, benchmark.py, executor.py, priorities.py, errors.py
├── analytics/               data_quality report, cost/completion aggregates
└── replay/                  backtest engine, walk-forward chronological splits

sdk/typescript/    thin client: spawns the real `goldenboy` CLI, validates
                    its --json output against the same protocol (no
                    reimplemented business logic)
skills/goldenboy/   SKILL.md — prompt-level integration, no runtime
schemas/            NEW (this audit): schemas/decision.schema.json — formal
                    JSON Schema for the Protocol, checked against both
                    language implementations
tests/              186 tests (Python) + 21 (TypeScript SDK), all passing
docs/               PROTOCOL.md, LANGUAGE_STRATEGY.md, DATASETS.md
benchmarks/results/ NEW (this audit): dated, reproducible scaling +
                    policy-validation reports
```

Total: **3,566 lines** of `goldenboy/` Python, **374 lines** of TypeScript
SDK source, **zero required runtime dependencies** (`pyproject.toml`:
`dependencies = []`; `tiktoken`/`anthropic`/`openai` are opt-in extras).
`sdk/typescript` has zero runtime dependencies of its own (`typescript` and
`@types/node` are devDependencies only).

CI (`.github/workflows/ci.yml`): Python 3.9–3.13 matrix (lint, type check,
test+coverage), a package-build-and-install-then-smoke-test job, a
`pip-audit` dependency-vulnerability job, and a dedicated `sdk-typescript`
job (typecheck, build, integration test against the real installed CLI).
Ubuntu-only today — see §8.

## 2. Bottlenecks — what's actually slow

Measured just now, this machine (Apple Silicon, macOS, Python 3.13.7),
`scripts/benchmark.py`:

| Operation | Latency |
|---|---|
| `RiskEngine.assess()` | sub-microsecond (pure arithmetic) |
| `Estimator.estimate_task()` [this repo] | ~22ms mean |
| CLI cold start (`goldenboy status`) | ~115ms mean |

None of these is a bottleneck in any conventional sense — a human issuing
one CLI command does not notice 115ms, and nothing here is called in a hot
loop. New this audit — `scripts/benchmark_scaling.py`, the "deliberately
large synthetic repository" benchmark `ROADMAP.md` listed as **Planned**
and, until now, not done (full tables in
`benchmarks/results/2026-09-15-scaling.md`):

- **Repo file count**: `_MAX_SCAN_FILES=200` genuinely bounds latency —
  48ms at 200 files, 51.6ms at 5,000 files (a 25x larger repo, +7% latency).
  The cap works as designed. No bottleneck, at any repo size, by
  construction.
- **Prompt token size**: this *does* scale with input size, close to
  linearly — 27ms at ~1K words, 2.1 **seconds** at ~10M words (tiktoken
  encoding of a very large string is genuinely CPU-bound). This is the one
  real, measured place a large-enough input produces multi-second latency.
  In practice, a single CLI-invocation prompt reaching 10M tokens (~40MB of
  text) is far outside how this tool is used — but it is the honest answer
  to "does anything here get slow at scale," and it's now measured instead
  of assumed away.
- **History log size**: `HistoryStore.load_events()` has *no* analogous
  cap (unlike the estimator's file walk) and scales linearly — 13ms at
  1MB/2.1K events, 136ms at 10MB/21K events, 1.46s at 100MB/214K events.
  For a local, single-user CLI history file this is not a problem today
  (214K recorded tasks would take years of heavy use to accumulate), but
  it is an unbounded read-the-whole-file-into-memory design, worth knowing
  about if that assumption ever changes.

## 3. What Python should own

Everything it already owns: `Budget`/`RiskEngine`/`Estimator`/
`TaskClassifier`/`DecisionEngine`/`GoldenBoyConfig`/`HistoryStore`/
`goldenboy.replay`. This is deterministic, pure-function-heavy logic with
zero I/O beyond local files, already typed (dataclasses throughout,
`mypy --strict`-adjacent config in `pyproject.toml`), already tested (186
tests), and — per §2 — not measurably slow. There is no part of this list
a different language would improve; moving any of it elsewhere would only
add a second implementation to keep in sync (the exact risk
`docs/PROTOCOL.md` already names for the *existing* Python/TypeScript
boundary).

## 4. Where TypeScript is (correctly) already used

`sdk/typescript/` — a thin client that spawns the real `goldenboy` CLI and
parses its `--json` output through `parseDecision`, which enforces the same
required fields `goldenboy.protocol.GoldenBoyDecision.from_dict` does. Zero
runtime dependencies, no reimplemented cost estimation/classification/risk
logic (verified by reading `client.ts`/`validate.ts` — there is no scoring
or threshold logic in the package at all). This is precisely the
"TypeScript CLI-and-agent-integration layer over a stable protocol" shape
a polyglot upgrade would otherwise be introducing from scratch — it exists,
is tested (21 passing tests, including 7 new schema-compatibility tests
added in this audit), and is exercised in CI against the real CLI.

A **second, independent** TypeScript CLI (reimplementing `analyze`/`plan`/
`run`/etc.'s logic rather than shelling out) was evaluated and rejected:
it would duplicate `Estimator`/`TaskClassifier`/`RiskEngine`/`DecisionEngine`
in a second language, which is the exact "no cost estimation ... exists
twice" principle `sdk/typescript/README.md` already documents. Node.js
startup latency is also not obviously better than Python's for this
workload — that would need its own measurement before being a reason to
duplicate anything, and no bottleneck exists to motivate collecting it (see
§2 — the actual complaint a duplicate CLI would need to fix doesn't exist).

## 5. Where Rust would help — today: nowhere, measured

No operation in §2 is CPU-bound at a scale this tool is actually used at.
The one operation that *is* CPU-bound at extreme scale (tiktoken-encoding a
~10M-token prompt, §2) is bounded by `tiktoken`'s own C/Rust-backed
implementation already — Golden Boy's Python code around it is not the
cost center. If a future benchmark shows the repo-scan or history-log paths
becoming real bottlenecks at a scale this project doesn't have today, the
ordering `docs/LANGUAGE_STRATEGY.md` already lays out remains correct,
re-confirmed by this audit's numbers:

1. `Estimator._estimate_codebase_context`'s file walk — already the
   slowest *of Golden Boy's own code*, already capped, already isolated
   behind one method call. (Per §2, the cap already works — this would
   only become relevant if a future need required removing the cap.)
2. `HistoryStore.load_events()` — uncapped today (§2), the more likely
   future candidate if local history ever reaches real scale.
3. `RiskEngine`/`DecisionEngine` arithmetic — last on purpose; it is
   sub-microsecond and moving it anywhere buys nothing.

## 6. Where a language should *not* be added

- **`RiskEngine`/`DecisionEngine` core arithmetic** — sub-microsecond;
  no version of "faster" is measurable here.
- **A second CLI implementation** (TypeScript or otherwise) — would
  duplicate business logic across languages, the one thing this project's
  own protocol design was built specifically to avoid.
- **Any ML component** (`task_classifier.py`, `policies.py`) — `ROADMAP.md`
  gates this on real labeled outcome data existing first; running
  `goldenboy replay --json` just now (see
  `benchmarks/results/2026-09-15-policy-validation.md`) confirms
  `dataset_size: 0` on this install — the gating condition is still
  unmet, for real, right now.
- **A server, database, or microservice split** — every transport in this
  project is a function call, CLI stdout, or a spawned child process; no
  concurrent-access or network-transparency need exists to justify one
  (see `docs/PROTOCOL.md`, "Why no server").

## 7. A real accuracy finding (not a language question)

> **Update (2026-09-17): fixed.** The finding below is preserved as-written
> (it was real, and the reasoning for not fixing it *in this audit*, at the
> time, was sound). It was subsequently fixed in the
> "evidence-driven intelligence & telemetry" upgrade —
> `Estimator._estimate_relevant_context` (context relevance, scored per-file
> from the task text rather than the whole repo) and
> `goldenboy.core.complexity` (an independent complexity signal). See
> CHANGELOG.md's "[Unreleased]" entry and `ROADMAP.md` for the before/after
> evidence (`benchmarks/results/2026-09-17-policy-validation-BEFORE-p0-fix.md`
> vs. `benchmarks/results/2026-09-17-policy-validation.md`: the same 8
> scenarios went from a uniform ~66.4–66.5% to 5.0%–28.5%, correctly
> differentiated).

Running the new workload-validation harness
(`scripts/validate_policy.py` → `benchmarks/results/2026-09-15-policy-validation.md`)
surfaced something worth flagging on its own: **`Estimator.estimate_task()`
returned the same ~66.4–66.5% cost estimate for all 8 scenario prompts**,
from `"Fix a typo in the login error message"` to `"Re-architect the data
model and migrate the storage layer to the new schema"`. This is because
`_estimate_codebase_context()` — a near-constant term when run repeatedly
from the same working directory — dominates `total_estimated_tokens` for
any normal-length prompt once the surrounding repository is even
moderately sized (this repository's own scanned source already sums to
~66,000 of the 100,000-token `max_budget_tokens` default). The consequence:
in a repo this size or larger, `estimated_cost_percentage` mostly measures
*how big the repo is*, not *how big the task is* — every task in this audit
landed on `complexity_label: HIGH` regardless of scope.

This is a real, reproducible behavior, not a hypothesis — but it is a
Python estimation-calibration question (whether `max_budget_tokens`'s
default is well-chosen for realistic repo sizes, or whether repo-context
weight should be decoupled from prompt-complexity weight), not something a
different language would change. It is out of scope for this audit to fix
unilaterally (`GoldenBoyPolicy`'s downstream behavior is intentional and
tested, and changing `Estimator`'s formula would change the estimated
percentage every existing test and user currently sees). Recorded here and
in `ROADMAP.md` as a flagged follow-up.

## 8. Maintenance risk

- **Hand-synced protocol.** `goldenboy/protocol.py` and
  `sdk/typescript/src/types.ts`/`validate.ts` are, by the project's own
  documentation, "kept in sync by hand." This audit adds
  `schemas/decision.schema.json` plus compatibility tests on both sides
  (`tests/test_protocol_schema.py`, `sdk/typescript/test/schema.test.ts`)
  that fail if the two drift — this reduces, but (being hand-authored
  enum lists on the TypeScript side) does not eliminate, the risk.
- **`cli.py` size.** 571 lines, 10 subcommands. `ROADMAP.md` already
  reclassifies a `cli/` package split as Planned-but-deferred, correctly,
  given the regression risk against its own extensive test coverage for a
  pure reorganization. Unchanged by this audit.
- **`HistoryStore.load_events()` has no size cap** (§2) — not a problem at
  today's realistic scale, but worth deciding on a cap or streaming read
  *before* it's a problem, not after.
- **CI is Ubuntu-only.** The `--json` CLI contract and the TypeScript SDK
  that spawns it are both used cross-platform in practice (a Windows
  developer running `npm install @goldenboy/sdk`); CI does not currently
  verify either the Python package or the SDK's subprocess-spawning path
  on macOS or Windows.

## 9. Migration risk

There is no migration in this audit's recommendation — see §10 — so the
migration risk considered here is the *counterfactual* risk of the
originally-scoped upgrade (Rust core + parallel TypeScript CLI), for the
record:

- **Distribution.** A Rust extension means per-platform compiled wheels
  (PyO3/maturin), replacing today's pure-Python, single-`pip install`
  story — a real cost with no offsetting measured benefit (§2, §5).
- **Drift.** A second, full TypeScript CLI reimplementing `analyze`/`plan`/
  etc. would need its cost/classification/risk logic to track the Python
  implementation forever, by hand, across every future change — the
  protocol boundary exists specifically so this never has to happen for
  the *existing* thin-client SDK; reintroducing it via a second CLI would
  undo that.
- **Toolchain surface.** Contributors would need a Rust toolchain
  (`cargo`, `maturin`) and a second Node/TypeScript build in addition to
  the current single `pip install -e ".[dev]"`, for components with no
  demonstrated need today.

## 10. Recommended architecture: unchanged, strengthened at the edges

**Do not add Rust. Do not add a second CLI implementation.** The existing
shape — Python core, thin TypeScript client, stable hand-documented
protocol, zero required runtime dependencies — is correct for this
project's actual measured size and workload, re-confirmed rather than
assumed by this audit. What this audit adds, all consistent with that
shape and none of it a new language:

1. `schemas/decision.schema.json` + cross-language compatibility tests
   (§8) — formalizes the protocol boundary that already existed informally.
2. `scripts/benchmark_scaling.py` + `benchmarks/results/2026-09-15-scaling.md`
   — closes the one benchmarking gap `ROADMAP.md` had open (large-repo
   behavior), confirming the existing caps work.
3. `scripts/validate_policy.py` + `benchmarks/results/2026-09-15-policy-validation.md`
   — exercises `DecisionEngine` and every baseline policy across a
   realistic task/budget matrix using real code paths, and surfaced the
   real finding in §7.
4. The §7 finding and §8 risks recorded in `ROADMAP.md` as follow-ups, not
   silently fixed.

See `POLYGLOT_UPGRADE_REPORT.md` for the before/after summary and the
final production-readiness verdict.

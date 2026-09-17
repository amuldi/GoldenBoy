<p align="center">
  <b>English</b> | <a href="README_zh.md">中文</a> | <a href="README_ja.md">日本語</a> | <a href="README_ko.md">한국어</a> | <a href="README_ar.md">العربية</a> | <a href="README_es.md">Español</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>AI Agent Resource Intelligence — spend less of your AI budget on the wrong work.</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-what-is-golden-boy">What is it</a> &nbsp;&middot;&nbsp;
  <a href="#-real-world-example">Example</a> &nbsp;&middot;&nbsp;
  <a href="#-key-capabilities">Capabilities</a> &nbsp;&middot;&nbsp;
  <a href="#-how-it-works">How it works</a> &nbsp;&middot;&nbsp;
  <a href="#-install">Install</a> &nbsp;&middot;&nbsp;
  <a href="#-cli-reference">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-protocol">Protocol</a> &nbsp;&middot;&nbsp;
  <a href="#-typescript-sdk">TypeScript SDK</a> &nbsp;&middot;&nbsp;
  <a href="#-replay-and-backtesting">Backtesting</a> &nbsp;&middot;&nbsp;
  <a href="#-telemetry-and-calibration">Calibration</a> &nbsp;&middot;&nbsp;
  <a href="#-validation">Validation</a> &nbsp;&middot;&nbsp;
  <a href="#-roadmap">Roadmap</a> &nbsp;&middot;&nbsp;
  <a href="#-contributing">Contributing</a>
</p>

> **Latest update (2026-09-17, protocol `1.1.0`):** fixed the P0 finding from the 2026-09-15 architecture
> audit — cost estimates were dominated by whole-repository size, not task size (the same ~66% for a typo
> fix and a full re-architecture). `Estimator` now scores which repo files a task's own wording actually
> points at (context relevance) and an independent, explainable complexity model, instead of scanning the
> whole repo — measured before/after in `benchmarks/results/2026-09-17-policy-validation*.md`. Also new:
> multi-label task classification, an execution-telemetry contract (`goldenboy report`), and estimate-vs-
> actual calibration (`goldenboy calibrate`). Full evidence in [`CHANGELOG.md`](CHANGELOG.md).

---

## 💡 What is Golden Boy?

AI coding agents tend to treat every task the same, regardless of how much usage is actually left. A large
task started at 15% remaining budget often ends the same way: interrupted mid-edit, with no record of
what was finished and what wasn't.

**Golden Boy** is a decision layer that sits between an agent and its work: it figures out what *kind* of
task this is, estimates what it will cost, checks that against remaining budget — *and how reliable that
budget reading actually is* — and tells the agent how aggressively to proceed: run it, keep going, reduce
scope, finish up and verify, or stop and checkpoint. Every recommendation ships with a confidence score and
a reason built from the actual numbers computed for that call, in the same versioned JSON shape
(the [Golden Boy Protocol](#-protocol)) whether you call it from Python, the CLI, or TypeScript.

| | |
|---|---|
| ✅ **It does** | Classify the task, estimate its cost, track budget + confidence, decide an action (run/continue/reduce scope/finish/verify/stop/ask), checkpoint deferred work, record what happened locally, and let you backtest alternative policies against that history. |
| 🚫 **It doesn't** | Decompose a task into a coding plan, replace the calling agent, act as a coding agent/IDE/LLM provider, or run a server. See [Design Principles](#-design-principles) and [About Task Breakdowns](#-about-task-breakdowns). |

---

## 🧠 Real-World Example

```
User: "Refactor the authentication system and update tests."
```

Every value below is real, live output from `goldenboy analyze` — not a mockup:

```bash
$ goldenboy analyze "Refactor the authentication system and update tests" --budget 6
--- Golden Boy Analysis: 'Refactor the authentication system and update tests' ---
Task type:        refactor (confidence: 0.47)
Also detected:    testing, architecture_change
Complexity:       LOW (0.20)
Complexity signals: test_requirement_keyword, refactor_keyword
Estimated cost:   29.42% (confidence: 0.85)
Remaining usage:  6.00% (exact, source: mock)
Risk:             LIMITED (ESTIMATED_COST_EXCEEDS_USABLE_BUDGET)
Decision:         REDUCE_SCOPE (confidence: 0.77)
Reason:           Task classified as refactor (LOW complexity, estimated cost 29.4% of budget, confidence 0.85). Remaining budget is 6.0% (exact via mock). Risk mode: LIMITED. Recommended action: REDUCE_SCOPE.
Recommendation:
  - Constrain remaining work to P0/P1 items.
  - Explicitly defer P2-P4 items and say so.
```

Nothing here is templated storytelling: the task type came from `TaskClassifier` actually scanning the
prompt text, the cost from `Estimator` actually scoring which files in *this* repo the task text points at
(not the whole repository — see [Key Capabilities](#-key-capabilities) below) plus the task's own complexity signals, and
the risk mode from `RiskEngine` actually comparing that cost to the mock budget you passed in. Change the
budget or the task text and every field changes with it — see [Protocol](#-protocol) for the exact JSON
this produces with `--json`.

---

## ✨ Key Capabilities

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 Task Intelligence</h3>
      <div>
        • 13-type classifier (bug fix, refactor, testing, architecture change, …), plus secondary types when more than one scores meaningfully<br>
        • Deterministic + transparent — a heuristic match-strength score, never a fake calibrated probability<br>
        • Complexity (LOW/MEDIUM/HIGH/VERY_HIGH) from an independent, explainable signal table — not back-computed from cost
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 Explained Decisions</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • Every decision ships a confidence score and a reason built from real numbers<br>
        • Confidence too low to act on safely → <code>ASK_USER</code> instead of guessing
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 Budget &amp; Confidence Tracking</h3>
      <div>
        • Remaining budget as a percentage, plus <b>EXACT / ESTIMATED / STALE / UNKNOWN</b> confidence<br>
        • A <code>STALE</code> or <code>UNKNOWN</code> reading can never quietly present itself as <code>SAFE</code><br>
        • Adapter staleness driven by an injectable clock — deterministic, no <code>sleep()</code> in tests
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 Checkpoint &amp; Resume</h3>
      <div>
        • Deferred work is saved, never silently dropped<br>
        • <code>goldenboy resume</code> replays from the last checkpoint<br>
        • Checkpoint schema is versioned — an incompatible future format fails cleanly
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 Local History &amp; Analytics</h3>
      <div>
        • Every decorated call appends one event locally — never raw task text<br>
        • Real Dataset Quality report (rows, corrupted/duplicate/invalid ratios)<br>
        • Cost/completion/failure-rate aggregates over your own real usage
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 Replay &amp; Backtesting</h3>
      <div>
        • 5 baseline policies scored against real history: precision, recall, premature-stop rate<br>
        • Walk-forward, leakage-safe chronological splitting<br>
        • Honest <code>N/A</code> below 10 events — never a fabricated table
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 Golden Boy Protocol</h3>
      <div>
        • One versioned, language-neutral JSON decision schema<br>
        • Strict validation — a specific error, never a raw <code>KeyError</code><br>
        • The same payload from Python, the CLI, and TypeScript
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 Agent Integrations</h3>
      <div>
        • <code>budget_aware_execution</code> decorator wraps any Python callable<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code> read real rate-limit headers<br>
        • A TypeScript SDK and a prompt-level <b>Claude Code</b> skill
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🎯 Context-Relevant Estimation</h3>
      <div>
        • Cost is scored from the repo context the task's own wording actually points at — not whole-repository size<br>
        • A task matching nothing in the repo reports zero relevant context (and lower confidence), never a repo-sized guess<br>
        • Repository size is still reported separately, for transparency, but no longer feeds the cost total
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>📈 Telemetry &amp; Calibration</h3>
      <div>
        • <code>goldenboy report</code>: record what an external agent actually observed (tokens, tests, verification status)<br>
        • <code>goldenboy calibrate</code>: MAE/RMSE/bias, estimated vs. actual, overall and per task type<br>
        • Honest <code>N/A</code> below 10 recorded samples — same convention as Replay &amp; Backtesting
      </div>
    </td>
  </tr>
</table>

---

## 🔄 How It Works

```
Task text
  │
  ├──► TaskClassifier        ──► TaskType (+ secondary types)
  ├──► Complexity model      ──► complexity score + named signals
  └──► Context relevance     ──► which repo files this task text
       (Estimator)                actually points at (not repo size)
                                     │
                                     ▼
                              Cost Estimate
                                     │
                                     ▼
                          Budget × Confidence
                     (EXACT · ESTIMATED · STALE · UNKNOWN)
                                     │
                 ┌───────────┬───────┴───────┬───────────┐
                 ▼           ▼               ▼           ▼
               SAFE      CAUTION         LIMITED     CRITICAL
                                     │
                                     ▼
                     Decision (RUN / CONTINUE / REDUCE_SCOPE /
                        FINISH / VERIFY / STOP / ASK_USER)
                                     │
                                     ▼
                    Record decision locally (HistoryStore)
                                     │
                                     ▼
              External agent executes ──► goldenboy report (actual telemetry)
                                     │
                                     ▼
        goldenboy calibrate (estimated vs. actual)  ·  goldenboy replay (backtest policies)
```

| Mode | Meaning | Agent behavior |
|---|---|---|
| 🟢 `SAFE` | Comfortably above estimated cost | Execute P0–P4 normally |
| 🟡 `CAUTION` | Sufficient, but the task is a large share of it | Keep going, but stay conservative and avoid opening new scope |
| 🟠 `LIMITED` | Estimated cost exceeds usable budget | Constrain to P0/P1, tell the caller what's being skipped |
| 🔴 `CRITICAL` | Budget already at/below its safety margin | Finish the current P0 unit, checkpoint, stop |

The mode is decided by two ordered checks — is the budget already exhausted (below its `safety_margin`)
→ `CRITICAL`; does the estimated cost exceed what's usable at all → `LIMITED` — and otherwise by the ratio
of estimated cost to usable budget, split at a configurable `caution_ratio` (default `0.5`). A `STALE`
budget reading is never allowed to produce a `SAFE` verdict — it's upgraded to at least `CAUTION`,
regardless of how comfortable the raw numbers look; `DecisionEngine` applies the same conservative rule to
`UNKNOWN`-confidence budgets (an adapter that's never been refreshed) as an explicit, separate policy on
top of the unchanged `RiskEngine` — see [`goldenboy/core/risk.py`](goldenboy/core/risk.py) and
[`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py).

---

## ⚖️ Before vs. After

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ Without Golden Boy</b>
      <p>An agent receives "refactor the entire authentication system," starts immediately, spends
      aggressively across exploration/implementation/tests, and gets interrupted mid-task when the budget
      runs out — with no record of what's done.</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ With Golden Boy</b>
      <p>The same request is classified, cost-estimated, and checked against budget <i>before</i> execution
      scope is committed — a real decision with a real confidence score, not a guess made after the fact.
      What actually happened is recorded locally, so the next similar task benefits from it.</p>
    </td>
  </tr>
</table>

---

## 🎬 Demo

A full arc — plan, then run adaptively against a shrinking budget, then diagnose the environment. Every
line below is real output, captured from this repo (nothing staged or shortened):

<details>
<summary><b>$ goldenboy plan "Refactor the entire authentication system" --budget 15</b></summary>

```
--- Execution Plan: 'Refactor the entire authentication system' ---
Remaining Budget: 15.00%
Estimated Cost (heuristic, based on prompt + relevant repo context + expected output): 5.00% (confidence: 0.59)
Risk Assessment: SAFE

Example unit breakdown (illustrative, not derived from the task above):
  [P0] Core feature implementation (Cost: 10.0%)
  [P1] Critical integration tests (Cost: 8.0%)
  [P2] Secondary cleanup (Cost: 5.0%)
  [P3] Animations / visual polish (Cost: 4.0%)
  [P4] Full documentation pass (Cost: 6.0%)
```

This repository has no `auth`/`authentication` module of its own, so `Estimator` correctly finds no
relevant file-path evidence for this specific task text here — cost floors at 5% and confidence drops
accordingly (see [Key Capabilities](#-key-capabilities)). The next command's `LIMITED` risk mode below comes from a
*different*, unrelated estimate (`Estimator.estimate_plan()` costing the illustrative example units
above, not this task's text — see the note in that command's own output).

</details>

<details>
<summary><b>$ goldenboy -v run "Refactor the auth module" --budget 15</b></summary>

```
[goldenboy.executor] [Refactor the auth module] Budget: 15.00% | Risk: LIMITED
[goldenboy.executor]   -> Executing: [P0] Core feature implementation
[goldenboy.executor]   -> Executing: [P1] Critical integration tests
[goldenboy.executor] Budget critically low. Triggering graceful stop.
[goldenboy.executor] Saving checkpoint for deferred work.
Starting Task: 'Refactor the auth module'
Note: this uses the illustrative example plan (see 'goldenboy plan --help'); it does not decompose the task text above into real units.

--- Result ---
Task 'Refactor the auth module' finished. Completed 1 units. Deferred 4 units.

Deferred Work:
  - [P1] Critical integration tests
  - [P2] Secondary cleanup
  - [P3] Animations / visual polish
  - [P4] Full documentation pass
```

Budget dropped below the safety margin mid-run — the executor finished its current unit, checkpointed
the rest, and stopped instead of continuing to spend.

</details>

<details>
<summary><b>$ goldenboy validate</b> (fresh install, no history yet)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

No numbers are invented to fill in for data that doesn't exist yet — see [History & Analytics](#-history-and-analytics).

</details>

<details>
<summary><b>$ goldenboy doctor</b></summary>

```
--- Golden Boy Doctor ---
Python: 3.13.7
Optional dependency 'tiktoken': installed
Optional dependency 'anthropic': installed
  Anthropic API key: not configured (ANTHROPIC_API_KEY not set)
Optional dependency 'openai': installed
  OpenAI API key: not configured (OPENAI_API_KEY not set)
Config: OK (safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0)
Checkpoint: none present
```

API key presence is reported, never the value itself — every diagnostic command (`doctor`, `status`,
`validate`) also supports `--json`.

</details>

---

## 🚀 Install

```bash
pip install goldenboy
goldenboy --help
```

Or from source:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

The core install has **no required third-party dependencies**. Optional extras add specific capabilities:

```bash
pip install "goldenboy[tiktoken]"   # exact token counts (falls back to a coarser heuristic without it)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

TypeScript agents/tools can use [`sdk/typescript`](sdk/typescript) instead of calling the CLI directly —
see [TypeScript SDK](#-typescript-sdk).

---

## ⚡ Quick Start

```bash
goldenboy analyze "Refactor the authentication system"   # full recommendation: type, risk, action, why
goldenboy status                                          # current budget and any pending checkpoint
goldenboy validate                                         # config + checkpoint + local data-quality report
goldenboy doctor                                            # environment, config, and checkpoint diagnostics
```

---

## 🖥 CLI Reference

| Command | Purpose |
|---|---|
| `goldenboy analyze <task>` | Full task-intelligence recommendation: type, complexity, risk, action, confidence, reason. `--progress 0.0-1.0`, `--json`. |
| `goldenboy plan <task>` | Estimate a task's real cost from its text + the repo context actually relevant to it, and show the resulting risk mode. |
| `goldenboy run <task>` | Execute a budget-aware demo plan adaptively against a mock budget. |
| `goldenboy status` | Inspect current budget and any pending checkpoint. `--json`. |
| `goldenboy resume` | Resume execution from the previous checkpoint. |
| `goldenboy doctor` | Diagnose Python version, optional dependencies, provider key configuration, config, checkpoint. `--json`. |
| `goldenboy validate` | Validate config + checkpoint + local history data quality; exits 1 on a real problem. `--json`. |
| `goldenboy replay` | Backtest baseline policies against local (or `--dataset PATH`) history. `--json`. |
| `goldenboy benchmark` | Measure estimator/risk-engine/CLI-startup latency, on this machine, now. `--json`. |
| `goldenboy report` | Record actual execution telemetry for a task Golden Boy previously analyzed. `--outcome` (required) plus optional fields, or `--json-file PATH`. |
| `goldenboy calibrate` | Compare estimated vs. actual cost (MAE/RMSE/bias) over recorded telemetry. `--dataset PATH`, `--json`. |
| `goldenboy export` | Export config + checkpoint + history as one reproducible JSON document. `--output PATH`. |

Add `--budget` to any mock-budget command to control the starting budget, and `-v`/`--verbose` (before the
subcommand) for the internal per-unit decision log shown in the [Demo](#-demo) above.

---

## 🐍 Python Integration

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # your real work goes here — Golden Boy decides whether to call it at all

refactor_auth()
```

`budget_aware_execution` asks the provider for a budget/mode decision and, only if the mode allows it,
calls your function — never the provider itself. Every call also records one event locally (never the raw
task text) — see [History & Analytics](#-history-and-analytics). The full public surface lives in
[`goldenboy/__init__.py`](goldenboy/__init__.py); anything not listed there is reachable via its own
submodule but isn't part of the stability contract the top-level API is.

For the full explained-decision API, use `DecisionEngine` directly:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 Protocol

Every decision Golden Boy produces — from Python, the CLI, or TypeScript — is one versioned,
language-neutral JSON shape: the **Golden Boy Protocol**. Full schema, versioning policy, and why there's
no server in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

```bash
goldenboy analyze "Refactor the auth module" --budget 6 --json
```

```jsonc
{
  "schema_version": "1.1.0",
  "task": {
    "task_type": "refactor", "complexity_label": "LOW", "estimated_cost_percentage": 5.0,
    "secondary_task_types": [], "complexity_signals": ["refactor_keyword"], "...": "..."
  },
  "usage": { "remaining_percentage": 6.0, "confidence": "EXACT", "...": "..." },
  "risk": { "mode": "LIMITED", "reason_code": "ESTIMATED_COST_EXCEEDS_USABLE_BUDGET" },
  "action": "reduce_scope",
  "confidence": 0.832,
  "reason": "Task classified as refactor (LOW complexity, ...). Recommended action: REDUCE_SCOPE.",
  "recommendation": ["Constrain remaining work to P0/P1 items.", "Explicitly defer P2-P4 items and say so."]
}
```

`goldenboy/protocol.py`'s `GoldenBoyDecision.from_dict`/`from_json` strictly validate any payload built
this way — a missing field or an incompatible major schema version raises `ProtocolError`, never a raw
`KeyError`. `sdk/typescript/src/validate.ts` enforces the identical contract on the TypeScript side.

---

## 📘 TypeScript SDK

[`sdk/typescript`](sdk/typescript) is a thin client, not a second implementation — it spawns the real
`goldenboy` CLI and parses its `--json` output through the same protocol validation described above. Zero
runtime dependencies; tests run on Node's built-in test runner, including real (non-mocked) integration
tests against the actual CLI.

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // uses `goldenboy` from PATH
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // built from the same real numbers as the Python/CLI output
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14 tests, including live CLI integration
```

See [`sdk/typescript/README.md`](sdk/typescript/README.md) for the full API and design notes.

---

## 📡 History and Analytics

Every `budget_aware_execution`-decorated call appends one event to a local, append-only log
(`.goldenboy/history.jsonl`, gitignored — same convention as the checkpoint file). An event never stores
the task's raw text, only its length and a truncated SHA-256 hash (see
[`goldenboy/core/history.py`](goldenboy/core/history.py) and [`SECURITY.md`](SECURITY.md)).

```bash
goldenboy validate   # Dataset Quality: rows, corrupted/duplicate/invalid-value ratios, GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # config + checkpoint + history (quality report, analytics, events) as one JSON document
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # a real report -- "NO_DATA" if nothing's recorded yet
print(analyze(store).render())                  # cost/completion/failure-rate aggregates, or "N/A"
```

On a fresh install both report zero rows honestly — see the [Demo](#-demo)'s `validate` example above.
Nothing here is a placeholder waiting to be "unlocked": it's real, working code that starts producing real
aggregates the moment your agent actually runs decorated tasks.

---

## 🔁 Replay and Backtesting

`goldenboy.replay` answers one question: *would a different resource-allocation policy have made better
decisions on these actual past tasks?* This is an **AI agent resource-allocation backtest**, not a
financial one. Five policies are compared on identical footing — two fixed-threshold baselines (15%/20%),
a complexity-only heuristic, a usage-only heuristic, and `GoldenBoyPolicy` (which wraps the real,
unmodified `RiskEngine`) — via `goldenboy.core.policies` and `goldenboy.replay.engine`.

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

That's the real, current output on a fresh install — and it's supposed to be. There is no bundled or
synthetic dataset standing in for real usage; `docs/DATASETS.md` documents why public benchmarks like
SWE-bench don't substitute for it (they measure code-generation correctness, not budget-aware resource
decisions). Once your own `.goldenboy/history.jsonl` has at least 10 events, `goldenboy replay` scores
every policy for real:

```
Policy                        Precision     Recall   Accuracy  PrematureStop  UnnecessaryContinue
---------------------------------------------------------------------------------------------------
fixed_threshold_15pct            ...           ...       ...          ...              ...
golden_boy_risk_engine           ...           ...       ...          ...              ...

Limitations:
  - Off-policy evaluation from logged outcomes: an event's recorded outcome reflects the decision
    Golden Boy actually made at the time, not the alternate policy being scored here. This is a
    descriptive comparison on existing data, not a causal guarantee of future behavior.
  - ...
```

`walk_forward_folds()` chronologically partitions events with no leakage across fold boundaries — tested,
ready infrastructure for a future learned policy (today's five policies are all fixed/deterministic, so
folding doesn't change their scores yet; see `goldenboy/replay/engine.py`'s module docstring). The report
always prints its own methodology limitations alongside any numbers — see
[`goldenboy/replay/engine.py`](goldenboy/replay/engine.py).

---

## 📈 Telemetry and Calibration

Golden Boy estimates a cost *before* work happens; it has no way to observe what actually happened
afterward unless something tells it. `goldenboy report` is that contract — record what an external agent
(you, or whatever executed the task) actually measured, echoing back the estimate it was compared against:

```bash
$ goldenboy report --outcome completed --task-type bug_fix \
    --estimated-cost-percentage 8.0 --actual-total-tokens 9000
Recorded telemetry: outcome=completed, actual_cost=9.00%
```

Only `--outcome` is required — every other field (`--verification-status`, `--tests-run`/`--tests-passed`,
`--files-touched`, `--duration-seconds`, …) is optional, and none of them ever include your prompt or code;
see [`goldenboy/core/telemetry.py`](goldenboy/core/telemetry.py) for the full field contract and
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md) for the verification-status vocabulary
(`VERIFIED`/`PARTIALLY_VERIFIED`/`UNVERIFIED`/`FAILED`) that distinguishes a *claimed* outcome from a
*verified* one.

Once at least 10 telemetry records exist, `goldenboy calibrate` compares estimated against actual cost —
same honest floor as `goldenboy replay`:

```bash
$ goldenboy calibrate
Calibration (estimated vs. actual cost percentage): n=0 (need >= 10) -- N/A, insufficient data
```

That's real output on a fresh install (zero recorded telemetry is the honest starting state — see
[Limitations](#-limitations)). With real data, it reports MAE, RMSE, median absolute error, bias
(`mean(actual - estimated)`; positive means Golden Boy underestimates on average), and over-/under-
estimation rates, both overall and broken out per task type — see
[`goldenboy/core/calibration.py`](goldenboy/core/calibration.py).

---

## 🔌 Integrations

Provider adapters report usage; they never execute your code. Real work always runs through the
`budget_aware_execution` decorator above.

| Provider | Reads | Notes |
|---|---|---|
| `MockProvider` | A synthetic, in-memory percentage | For demos and tests — no network calls. |
| `AnthropicAdapter` | `anthropic-ratelimit-tokens-remaining` / `-limit` response headers | Requires `goldenboy[anthropic]`. Reflects the org's *shared* rate limit, not this call alone. |
| `OpenAIAdapter` | `x-ratelimit-remaining-tokens` / `-limit-tokens` response headers | Requires `goldenboy[openai]`. Same shared-limit caveat as above. |
| Claude Code skill | The `<total_tokens>` figure Claude Code injects into context | No Python process required — see below. |
| TypeScript SDK | The `goldenboy` CLI's `--json` output over a spawned process | No HTTP server — see [Protocol](#-protocol). |

```python
from goldenboy.adapters.anthropic_adapter import AnthropicAdapter
from goldenboy.integration import budget_aware_execution
from goldenboy.core.priorities import Priority

adapter = AnthropicAdapter()
adapter.refresh_usage()

@budget_aware_execution(adapter, "1", "Refactor auth module", Priority.P1)
def refactor_auth():
    ...
```

Both adapters only update their reading via an explicit `refresh_usage()` call, and track how long ago
that happened using an injectable clock — past `stale_after_seconds` (default 300s), confidence ages from
`ESTIMATED` to `STALE` on its own. Before the first refresh, confidence is `UNKNOWN` —
`DecisionEngine` (not `RiskEngine` itself) treats that conservatively too, the same way it treats `STALE`.

**Claude Code** gets a prompt-level integration instead:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md) teaches an LLM agent to read the remaining-usage
figure Claude Code injects directly into context and reason about its own execution mode, with the exact
same `SAFE`/`CAUTION`/`LIMITED`/`CRITICAL` vocabulary as `goldenboy.core.risk.ExecutionMode` — kept in
sync by hand, not shared code, since one side is Python and the other is a prompt.

---

## 🏗 Architecture

<details>
<summary><b>Click to expand the package tree</b></summary>

```
goldenboy/
├── __init__.py            # small, deliberate public API
├── cli.py                  # status / plan / run / resume / doctor / analyze / validate / replay / benchmark / export
├── protocol.py              # the Golden Boy Protocol -- GoldenBoyDecision schema + validation
├── integration.py           # budget_aware_execution decorator + history recording
├── adapters/
│   ├── base.py               # ProviderAdapter interface + shared staleness logic
│   ├── mock.py                # synthetic provider for demos/tests
│   ├── anthropic_adapter.py
│   └── openai_adapter.py
├── core/
│   ├── budget.py               # Budget, UsageConfidence
│   ├── estimator.py            # task cost estimation
│   ├── risk.py                  # RiskEngine → ExecutionMode
│   ├── executor.py              # AdaptiveExecutor
│   ├── checkpoint.py            # CheckpointManager
│   ├── config.py                 # GoldenBoyConfig
│   ├── priorities.py             # Priority, ExecutionUnit
│   ├── task_types.py             # TaskType, DecisionAction vocabularies
│   ├── task_classifier.py         # TaskClassifier -- deterministic keyword classification
│   ├── decision_engine.py         # DecisionEngine -- the full explained GoldenBoyDecision
│   ├── history.py                  # HistoryStore, TaskEvent -- local event log
│   ├── policies.py                  # baseline policies + GoldenBoyPolicy, for replay
│   ├── benchmark.py                  # shared benchmark implementation (CLI + scripts/benchmark.py)
│   └── errors.py                      # GoldenBoyError, ConfigError, CheckpointError
├── analytics/
│   ├── data_quality.py         # Dataset Quality report over the local history log
│   └── engine.py                 # cost/completion/failure-rate aggregates
└── replay/
    └── engine.py               # run_backtest, walk_forward_folds

sdk/typescript/               # thin TypeScript client -- see the SDK section above
├── src/{types,client,validate,errors,index}.ts
└── test/                      # real integration tests against the actual CLI

docs/
├── PROTOCOL.md              # Golden Boy Protocol schema + versioning policy
├── DATASETS.md               # dataset/research landscape review
└── LANGUAGE_STRATEGY.md       # why Python, why TypeScript where it is, why not Rust yet
```

</details>

---

## ⚙️ Configuration

Every policy threshold lives in `GoldenBoyConfig`, with this override order:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| Field | Env var | Default | Meaning |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | Percentage points reserved below reported remaining budget before it counts as exhausted. |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | Estimated-cost/usable-budget ratio at which risk moves from SAFE to CAUTION. |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | Fallback per-unit cost when a plan's units don't declare one. |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | Token count treated as "100% of budget" when converting a raw token estimate into a percentage. |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | How long a refreshed provider reading stays `ESTIMATED` before aging to `STALE`. |

Out-of-range values, malformed JSON, and unparseable `GOLDENBOY_*` env vars all raise a clear
`ConfigError` — at the CLI, a one-line `error:` message and exit `1`, never a stack trace.

---

## 🧭 Design Principles

- **Lightweight** — the core install has no required third-party runtime dependencies; provider SDKs and the TypeScript SDK's own tooling are opt-in.
- **Adaptive** — execution behavior changes with remaining budget *and* with how much to trust that number: a `STALE` or `UNKNOWN` reading can never produce a `SAFE` verdict.
- **Deterministic** — identical inputs produce identical decisions. The estimator, classifier, and risk engine have no hidden randomness; adapter staleness is driven by an injectable clock, so it's testable without sleeping.
- **Provider-optional** — `import goldenboy` never requires `anthropic` or `openai` to be installed.
- **Agent-first** — Golden Boy decides how aggressively an agent should proceed based on the remaining budget. The calling agent remains responsible for understanding and decomposing the task.
- **Fail safely** — malformed config, corrupted checkpoints, and invalid input produce a specific, human-readable error and exit code, never a raw traceback or silent data loss.
- **Evidence over complexity** — no fabricated benchmark numbers, backtest results, or historical datasets, anywhere. `goldenboy replay`/`goldenboy.analytics` report `N/A`/`NO_DATA` rather than invent a baseline; see [`docs/DATASETS.md`](docs/DATASETS.md) and [`ROADMAP.md`](ROADMAP.md)'s explicit non-goals.

---

## 📦 About Task Breakdowns

> The estimated cost shown by `plan`/`run`/`analyze` is computed from the actual task text and repository
> context — that number is real. The `plan`/`run` unit breakdown is **illustrative**: it is not an
> LLM-generated decomposition of your task. Golden Boy intentionally keeps its core dependency-free and
> out of the business of understanding *how* to do a task; actual task decomposition remains the
> responsibility of the calling agent (see [Design Principles](#-design-principles)). `TaskClassifier`
> tells you *what kind* of task it looks like, not how to break it into steps.

---

## ⚠️ Limitations

- Cost estimates are heuristic — prompt length, a bounded scan of the repo files the task's own wording gives evidence for, and an expected-output size scaled by a fixed complexity-signal table — not billing guarantees, and not a model of what an agent would actually load into context.
- Context relevance is deterministic path/keyword matching (see [Key Capabilities](#-key-capabilities)), not semantic understanding. A task whose wording doesn't textually match any file path in the repo reports zero relevant context (with lower confidence) even if the task is, in fact, relevant to that repo — it is a recall-oriented heuristic, not a guarantee of finding every actually-relevant file.
- `TaskClassifier` is a deterministic keyword matcher, not a trained model — its confidence score reflects match strength, not a calibrated probability. Same for the independent complexity score (`goldenboy.core.complexity`): a `0.72` means "this task matched signals totaling 0.72 of a fixed weight table," not "72% probability of anything." Neither has labeled real-world data to train/calibrate against yet (see `docs/DATASETS.md`).
- `goldenboy replay`/`goldenboy.analytics` report `N/A`/`NO_DATA`, and `goldenboy calibrate` reports insufficient-data, until at least 10 real events/telemetry records are recorded locally — there is no bundled dataset standing in for either.
- Replay's metrics are off-policy evaluation from logged outcomes: an event's recorded outcome reflects the decision Golden Boy actually made, not the alternate policy being scored — a descriptive comparison, not a causal guarantee (see [Replay and Backtesting](#-replay-and-backtesting)).
- Calibration depends entirely on external agents actually calling `goldenboy report` — Golden Boy cannot observe execution outcomes on its own, and a `verification_status` of `VERIFIED` is only as trustworthy as whoever reported it; Golden Boy has no way to independently confirm a claimed verification.
- Provider usage (rate-limit headers) can change outside Golden Boy's control between refreshes; that's exactly what `STALE` confidence exists to flag.
- The `plan`/`run` unit breakdown is illustrative, not task decomposition (see above).
- Golden Boy does not replace the calling coding agent's own judgment — it only informs how much to attempt.

---

## ✅ Validation

Golden Boy is validated, as of 2026-09-17 (protocol `1.1.0`), against:

- **247 Python tests**, 95% line coverage (`pytest --cov`) — up from 186 tests / 95% on 2026-09-14 (the estimator/complexity/telemetry/calibration/multi-label upgrade added 61 tests; see CHANGELOG.md)
- **21 TypeScript tests** (`npm test` in `sdk/typescript`), including real (non-mocked) integration tests against the actual installed CLI
- Ruff and mypy clean, this environment (mypy 2.3.1) — mypy 1.19.1 compatibility was verified on 2026-09-14 and not independently re-run on 2026-09-17; CI (`mypy` job) checks the installed resolver's version on every push
- `pip-audit`: 0 known vulnerabilities (re-run 2026-09-17)
- Python 3.9–3.13, on GitHub Actions (Ubuntu only — see [Limitations](#-limitations) and `ARCHITECTURE_AUDIT.md` §8 on cross-platform CI)
- A built wheel and sdist installed into an independent, fresh virtual environment, with every CLI command (including `report`/`calibrate`) exercised against it
- A core-only install (`pip install goldenboy`) pulling zero third-party runtime dependencies — verified live via `pip list` against a clean-room install, not merely asserted

CI (`.github/workflows/ci.yml`, 8 jobs):

| Job | Result |
|---|---|
| security (pip-audit) | ✓ |
| test (3.9) | ✓ |
| test (3.10) | ✓ |
| test (3.11) | ✓ |
| test (3.12) | ✓ |
| test (3.13) | ✓ |
| build (wheel install + every CLI command + benchmark sanity check) | ✓ |
| sdk-typescript (real integration against the installed CLI) | ✓ |

---

## 📊 Benchmarks

Measured locally (Apple M1 Pro, macOS arm64, Python 3.13.7) via `goldenboy benchmark` /
`scripts/benchmark.py` (one shared implementation — see `goldenboy/core/benchmark.py`) — not part of CI's
pass/fail gate (CI only checks the numbers are non-negative and the estimator is deterministic), not a
guarantee. Re-run it yourself before relying on these numbers for anything.

| Operation | Mean | Median | n |
|---|---|---|---|
| `Estimator.estimate_task()` (warm, this repo, 2026-09-17) | 41.44ms | 40.81ms | 20 |
| `Estimator.estimate_task()` determinism | PASS — 1 distinct result across 10 identical calls | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| CLI cold start (`goldenboy status`) | 119.09ms | 118.73ms | 5 |

`RiskEngine.assess()` is pure arithmetic on already-computed values, so it's sub-microsecond by
construction. `Estimator.estimate_task()` went from 9.30ms (2026-09-13) to 41.44ms (2026-09-17) — a real,
measured increase, not noise: it now walks the repo tree twice (once for the whole-repo size figure, once
scoring which files the task text actually points at — see [Key Capabilities](#-key-capabilities)) plus
scores the task's own complexity signals. Still bounded by `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` and still
imperceptible next to CLI cold start; see `BENCHMARKS.md`'s 2026-09-17 entry and
`benchmarks/results/2026-09-17-scaling.md` for the full repo-size/prompt-size scaling curves. CLI cold
start is mostly Python interpreter/import overhead — it's what you actually feel running any single
`goldenboy` command. Full methodology, caveats, and the Rust-migration reasoning built on these numbers:
[`BENCHMARKS.md`](BENCHMARKS.md) and [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md).

---

## 🗺 Roadmap

**Shipped, tested, real:**

- ✓ Task-aware cost estimation from *relevant* repo context (not whole-repo size) + an independent, explainable complexity model, adaptive execution modes, checkpoint/defer/resume, usage confidence incl. STALE detection
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`report`/`calibrate`/`benchmark`/`export`)
- ✓ Anthropic/OpenAI provider adapters, Claude Code skill integration
- ✓ Golden Boy Protocol (versioned, language-neutral) + TypeScript SDK
- ✓ Task classification (`TaskClassifier`, incl. secondary types) + `DecisionEngine` (explained action/confidence/reason)
- ✓ Local history (`HistoryStore`) + data-quality/analytics reports
- ✓ Baseline policies + `goldenboy.replay` backtest engine + walk-forward splitting
- ✓ Execution telemetry contract (`ExecutionTelemetry`/`TelemetryStore`) + `goldenboy.core.calibration` (estimated-vs-actual MAE/RMSE/bias)
- ✓ Benchmarking against deliberately large synthetic repos/history logs (`scripts/benchmark_scaling.py`)

| Direction | Status |
|---|---|
| A real, populated backtest/calibration result (not `N/A`/insufficient-data) | Blocked on real usage data + telemetry accumulating — cannot be produced honestly today |
| A learned task classifier / policy | Research — needs real labeled outcome data first |
| Split `cli.py` into a `cli/` package | Planned — deferred this cycle (regression risk vs. benefit; see `ROADMAP.md`) |
| Cross-platform CI (macOS/Windows smoke tests) | Planned — see `ARCHITECTURE_AUDIT.md` §8 |
| `HistoryStore`/`TelemetryStore` streaming reads at very large log sizes | Planned — measured fine through 100MB/~214K events (`benchmarks/results/2026-09-17-scaling.md`); not yet a real problem |
| Additional agent integrations (e.g. Codex) | Research — only with a real, documented usage signal to build against |

Nothing above is claimed production-ready unless it's also covered by tests. Full breakdown of
Done/Planned/Research, including explicit non-goals (no database, no web dashboard, no server, no premature
ML or Rust), in [`ROADMAP.md`](ROADMAP.md).

---

## 🤝 Contributing

Contributions are welcome. [`CONTRIBUTING.md`](CONTRIBUTING.md) has the setup steps, the checks a PR is
expected to pass (`pytest`, `ruff`, `mypy`, `python -m build` — all enforced in CI), and the engineering
principles review is held to: existing architecture first, root cause over symptom, no fake completeness,
honest confidence labeling, and no hardcoded policy numbers outside `GoldenBoyConfig`.

---

## 🛠 Development

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest --cov=goldenboy --cov-report=term-missing
ruff check goldenboy tests scripts run_tests.py
mypy
```

For the TypeScript SDK:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 More Docs

| Doc | Covers |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | The Golden Boy Protocol schema, versioning policy, and why there's no server. |
| [`docs/DATASETS.md`](docs/DATASETS.md) | Dataset/research landscape review (SWE-bench, HumanEval, LiveCodeBench, RepoBench, token-consumption research) and why none of them substitute for `HistoryStore`. |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | Why Python remains the core, where TypeScript is used, and the future Rust migration boundary. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed release to release. |
| [`ROADMAP.md`](ROADMAP.md) | Full Done / Planned / Research breakdown, including explicit non-goals. |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Measured performance numbers, methodology, and what isn't measured yet. |
| [`SECURITY.md`](SECURITY.md) | How credentials and local history are handled, and how to report a vulnerability. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Setup, checks, and the engineering principles reviews are held to. |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | TypeScript SDK API reference and design notes. |

---

## 📄 License

[MIT](LICENSE).

<p align="center">
  ⭐ If Golden Boy saves your agent from burning through its budget, a star helps more people find it.
</p>

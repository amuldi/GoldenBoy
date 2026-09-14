<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>Spend less of your AI budget on the wrong work.</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-93%25-2ea44f?style=flat-square" alt="Coverage 93%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-what-is-golden-boy">What is it</a> &nbsp;&middot;&nbsp;
  <a href="#-key-capabilities">Capabilities</a> &nbsp;&middot;&nbsp;
  <a href="#-how-it-works">How it works</a> &nbsp;&middot;&nbsp;
  <a href="#-demo">Demo</a> &nbsp;&middot;&nbsp;
  <a href="#-install">Install</a> &nbsp;&middot;&nbsp;
  <a href="#-cli-reference">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-integrations">Integrations</a> &nbsp;&middot;&nbsp;
  <a href="#-validation">Validation</a> &nbsp;&middot;&nbsp;
  <a href="#-roadmap">Roadmap</a> &nbsp;&middot;&nbsp;
  <a href="#-contributing">Contributing</a>
</p>

---

## 💡 What is Golden Boy?

AI coding agents tend to treat every task the same, regardless of how much usage is actually left. A large
task started at 15% remaining budget often ends the same way: interrupted mid-edit, with no record of
what was finished and what wasn't.

**Golden Boy** is a small decision layer that sits between an agent and its work: it estimates what a task
will cost, checks that against remaining budget — *and how reliable that budget reading actually is* — and
tells the agent how aggressively to proceed: normally, cautiously, in a reduced scope, or not at all until
it checkpoints and stops.

| | |
|---|---|
| ✅ **It does** | Estimate task cost, track budget + confidence, pick an execution mode, checkpoint/defer/resume work, and expose all of it through a CLI and a Python decorator. |
| 🚫 **It doesn't** | Decompose a task into a coding plan, replace the calling agent, or act as a coding agent, IDE, or LLM provider itself. See [Design Principles](#-design-principles) and [About Task Breakdowns](#-about-task-breakdowns). |

---

## ✨ Key Capabilities

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>📐 Task Cost Estimation</h3>
      <div>
        • Combines actual prompt text with a bounded repository scan<br>
        • Exact token counts via <code>tiktoken</code> when installed, a coarser heuristic otherwise<br>
        • Every estimate ships with a confidence score, never a bare number
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔋 Budget &amp; Confidence Tracking</h3>
      <div>
        • Remaining budget as a percentage, plus <b>EXACT / ESTIMATED / STALE / UNKNOWN</b> confidence<br>
        • A <code>STALE</code> reading can never quietly present itself as <code>SAFE</code><br>
        • Confidence age is driven by an injectable clock — deterministic, no <code>sleep()</code> in tests
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🚦 Adaptive Risk Modes</h3>
      <div>
        • <b>SAFE → CAUTION → LIMITED → CRITICAL</b>, computed before work starts<br>
        • Split by a configurable estimated-cost / usable-budget ratio<br>
        • Already-exhausted budget short-circuits straight to <code>CRITICAL</code>
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 Checkpoint &amp; Resume</h3>
      <div>
        • Deferred work is saved, never silently dropped<br>
        • <code>goldenboy resume</code> replays from the last checkpoint<br>
        • Checkpoint schema is versioned — an incompatible future format fails cleanly, not silently
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🖥 CLI Diagnostics</h3>
      <div>
        • <code>plan</code> / <code>status</code> / <code>run</code> / <code>resume</code> / <code>doctor</code><br>
        • Real-time visibility into budget, risk mode, config, and environment<br>
        • <code>-v</code> surfaces the same per-unit decision log the executor makes internally
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 Agent Integrations</h3>
      <div>
        • <code>budget_aware_execution</code> decorator wraps any Python callable<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code> read real rate-limit headers<br>
        • A prompt-level <b>Claude Code</b> skill for agents with no Python process at all
      </div>
    </td>
  </tr>
</table>

---

## 🔄 How It Works

```
Task
  │
  ▼
Repository scan + prompt  ──►  Cost Estimate
                                     │
                                     ▼
                          Budget × Confidence
                     (EXACT · ESTIMATED · STALE · UNKNOWN)
                                     │
                 ┌───────────┬───────┴───────┬───────────┐
                 ▼           ▼               ▼           ▼
               SAFE      CAUTION         LIMITED     CRITICAL
            Proceed    Reduce scope,   Constrain to   Defer all but
                       stay cautious    P0/P1 only    P0, checkpoint,
                                                       stop
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
budget reading (usage fetched once, then not refreshed for a while) is never allowed to produce a `SAFE`
verdict — it's upgraded to at least `CAUTION`, regardless of how comfortable the raw numbers look. The
long-standing `UNKNOWN` default is left alone by design — see [`goldenboy/core/risk.py`](goldenboy/core/risk.py).

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
      <p>The same request goes through cost estimation and a budget check before execution scope is
      committed — risk is assessed <i>before</i> work starts, using the real budget and a real cost
      estimate, not a guess made after the fact.</p>
    </td>
  </tr>
</table>

```bash
$ goldenboy plan "Refactor the entire authentication system" --budget 15
--- Execution Plan: 'Refactor the entire authentication system' ---
Remaining Budget: 15.00%
Estimated Cost (heuristic, based on prompt + repo size): 25.37% (confidence: 0.85)
Risk Assessment: LIMITED
```

---

## 🎬 Demo

A full arc — plan, then run adaptively against a shrinking budget, then diagnose the environment. Every
line below is real output, captured from this repo (nothing staged or shortened):

<details>
<summary><b>$ goldenboy plan "Refactor the entire authentication system" --budget 15</b></summary>

```
--- Execution Plan: 'Refactor the entire authentication system' ---
Remaining Budget: 15.00%
Estimated Cost (heuristic, based on prompt + repo size): 25.37% (confidence: 0.85)
Risk Assessment: LIMITED

Example unit breakdown (illustrative, not derived from the task above):
  [P0] Core feature implementation (Cost: 10.0%)
  [P1] Critical integration tests (Cost: 8.0%)
  [P2] Secondary cleanup (Cost: 5.0%)
  [P3] Animations / visual polish (Cost: 4.0%)
  [P4] Full documentation pass (Cost: 6.0%)
```

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

API key presence is reported, never the value itself.

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

---

## ⚡ Quick Start

```bash
goldenboy plan "Refactor the authentication system"   # estimate cost + risk mode before doing anything
goldenboy status                                      # current budget and any pending checkpoint
goldenboy doctor                                      # environment, config, and checkpoint diagnostics
```

---

## 🖥 CLI Reference

| Command | Purpose |
|---|---|
| `goldenboy plan <task>` | Estimate a task's real cost from its text + repo size, and show the resulting risk mode. |
| `goldenboy run <task>` | Execute a budget-aware demo plan adaptively against a mock budget. |
| `goldenboy status` | Inspect current budget and any pending checkpoint. |
| `goldenboy resume` | Resume execution from the previous checkpoint. |
| `goldenboy doctor` | Diagnose Python version, optional dependencies, provider key configuration, config, and checkpoint state. |

Add `--budget` to any command to control the mock starting budget, and `-v`/`--verbose` (before the
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
calls your function — never the provider itself. The full public surface lives in
[`goldenboy/__init__.py`](goldenboy/__init__.py); anything not listed there is reachable via its own
submodule but isn't part of the stability contract the top-level API is.

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
`ESTIMATED` to `STALE` on its own.

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
├── __init__.py          # small, deliberate public API
├── cli.py                # status / plan / run / resume / doctor
├── integration.py        # budget_aware_execution decorator (the one real-execution entry point)
├── adapters/
│   ├── base.py            # ProviderAdapter interface + shared staleness logic
│   ├── mock.py            # synthetic provider for demos/tests
│   ├── anthropic_adapter.py
│   └── openai_adapter.py
└── core/
    ├── budget.py           # Budget, UsageConfidence
    ├── estimator.py        # task cost estimation
    ├── risk.py             # RiskEngine → ExecutionMode
    ├── executor.py         # AdaptiveExecutor
    ├── checkpoint.py       # CheckpointManager
    ├── config.py           # GoldenBoyConfig
    ├── priorities.py       # Priority, ExecutionUnit
    └── errors.py           # GoldenBoyError, ConfigError, CheckpointError
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

- **Lightweight** — the core install has no required third-party runtime dependencies; provider SDKs are opt-in extras.
- **Adaptive** — execution behavior changes with remaining budget *and* with how much to trust that number: a `STALE` reading can never produce a `SAFE` verdict.
- **Deterministic** — identical inputs produce identical decisions. The estimator and risk engine have no hidden randomness; adapter staleness is driven by an injectable clock, so it's testable without sleeping.
- **Provider-optional** — `import goldenboy` never requires `anthropic` or `openai` to be installed.
- **Agent-first** — Golden Boy decides how aggressively an agent should proceed based on the remaining budget. The calling agent remains responsible for understanding and decomposing the task.
- **Fail safely** — malformed config, corrupted checkpoints, and invalid input produce a specific, human-readable error and exit code, never a raw traceback or silent data loss.

---

## 📦 About Task Breakdowns

> The estimated cost shown by `plan`/`run` is computed from the actual task text and repository context —
> that number is real. The unit breakdown shown alongside it is **illustrative**: it is not an
> LLM-generated decomposition of your task. Golden Boy intentionally keeps its core dependency-free and
> out of the business of understanding tasks; actual task decomposition remains the responsibility of the
> calling agent (see [Design Principles](#-design-principles)).

---

## ⚠️ Limitations

- Cost estimates are heuristic (prompt length + a bounded repo scan) — not billing guarantees, and not a model of what an agent would actually load into context.
- Provider usage (rate-limit headers) can change outside Golden Boy's control between refreshes; that's exactly what `STALE` confidence exists to flag.
- The `plan`/`run` unit breakdown is illustrative, not task decomposition (see above).
- Golden Boy does not replace the calling coding agent's own judgment — it only informs how much to attempt.

---

## ✅ Validation

Golden Boy v1.0.0 is validated, as of 2026-09-13, against:

- 88 tests, 93% line coverage (`pytest --cov`)
- Ruff and mypy clean (mypy checked under both 1.19.1 and 2.3.1)
- `pip-audit`: 0 known vulnerabilities
- Python 3.9–3.13, on GitHub Actions
- A built wheel and sdist installed into independent, fresh virtual environments
- A core-only install (`pip install goldenboy`) pulling zero third-party runtime dependencies

CI (`.github/workflows/ci.yml`, 7 jobs):

| Job | Result |
|---|---|
| security (pip-audit) | ✓ |
| test (3.9) | ✓ |
| test (3.10) | ✓ |
| test (3.11) | ✓ |
| test (3.12) | ✓ |
| test (3.13) | ✓ |
| build (wheel install + CLI smoke test) | ✓ |

---

## 📊 Benchmarks

Measured once, locally (Apple M1 Pro, macOS arm64, Python 3.13.7, 2026-09-13) via `scripts/benchmark.py` —
not part of CI, not a guarantee. Re-run it yourself before relying on these numbers for anything.

| Operation | Mean | Median | n |
|---|---|---|---|
| `Estimator.estimate_task()` (warm, this repo) | 9.30ms | 8.79ms | 20 |
| `Estimator.estimate_task()` determinism | PASS — 1 distinct result across 10 identical calls | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| CLI cold start (`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()` is pure arithmetic on already-computed values, so it's sub-microsecond by
construction. Estimator latency scales with repository size (bounded by the `_MAX_SCAN_FILES` /
`_MAX_FILE_BYTES` caps), not prompt length. CLI cold start is mostly Python interpreter/import overhead —
it's what you actually feel running any single `goldenboy` command. Full methodology and caveats in
[`BENCHMARKS.md`](BENCHMARKS.md).

---

## 🗺 Roadmap

**v1.0 — done, tested, shipped:**

- ✓ Task-aware cost estimation
- ✓ Adaptive execution modes (SAFE/CAUTION/LIMITED/CRITICAL)
- ✓ Checkpoint/defer/resume
- ✓ Usage confidence, including STALE detection
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`)
- ✓ Anthropic/OpenAI provider adapters
- ✓ Claude Code skill integration

| Direction | Status |
|---|---|
| Additional agent integrations | Research — only if a real, documented usage signal exists to build against |
| `goldenboy history` (past checkpoints, mode transitions over time) | Research — needs a persistence story first |
| Benchmarking behavior against a deliberately large synthetic repo | Planned |
| Benchmarking real provider-adapter latency (`refresh_usage()`) | Research — would mostly measure network conditions, not Golden Boy itself |

Nothing above is claimed production-ready unless it's also covered by tests. Full breakdown of
Done/Planned/Research in [`ROADMAP.md`](ROADMAP.md).

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

---

## 📚 More Docs

| Doc | Covers |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | What changed release to release. |
| [`ROADMAP.md`](ROADMAP.md) | Full Done / Planned / Research breakdown, including explicit non-goals. |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Measured performance numbers, methodology, and what isn't measured yet. |
| [`SECURITY.md`](SECURITY.md) | How credentials are handled and how to report a vulnerability. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Setup, checks, and the engineering principles reviews are held to. |

---

## 📄 License

[MIT](LICENSE).

<p align="center">
  ⭐ If Golden Boy saves your agent from burning through its budget, a star helps more people find it.
</p>

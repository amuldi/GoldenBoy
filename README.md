<p align="center">
  <picture>
    <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="180" alt="Golden Boy">
  </picture>
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><em>Spend less of your AI budget on the wrong work.</em></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-111111?style=flat-square" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-93%25-111111?style=flat-square" alt="Coverage 93%">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
A lightweight budget-aware execution layer for AI coding agents. Golden Boy estimates task cost,
tracks how much usage is left (and how much to trust that number), and adapts execution intensity
before an agent burns through its budget.
</p>

---

## What is Golden Boy?

AI coding agents tend to treat every task the same, regardless of how much usage is actually left.
A large task started at 15% remaining budget often ends the same way: interrupted mid-edit, with no
record of what was finished and what wasn't.

Golden Boy is a small decision layer that sits between an agent and its work: it estimates what a task
will cost, checks that against remaining budget (and how reliable that budget reading actually is), and
tells the agent how aggressively to proceed — normally, cautiously, in a reduced scope, or not at all
until it checkpoints and stops.

It does this:

- **Estimates task cost** from the actual prompt text and repository size (`Estimator`)
- **Tracks budget and its own confidence in that number** — exact, estimated, stale, or unknown (`Budget`, `UsageConfidence`)
- **Picks an execution mode** — SAFE, CAUTION, LIMITED, or CRITICAL (`RiskEngine`)
- **Checkpoints and defers** work instead of failing silently mid-task (`CheckpointManager`)
- **Reports diagnostics** through a CLI (`goldenboy doctor`, `status`, `plan`)
- **Integrates with a calling agent** — as a Python decorator, or as a prompt-level skill for LLM agents

It does **not** decompose a task into a coding plan, replace the calling agent, or act as a coding agent,
IDE, or LLM provider itself — see [Design principles](#design-principles) and
[About task breakdowns](#about-task-breakdowns) below.

## How it works

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

A `STALE` budget reading (usage fetched once, then not refreshed for a while) is never allowed to
produce a `SAFE` verdict — it's treated as at least `CAUTION`, regardless of how comfortable the raw
numbers look. See [Design principles](#design-principles).

## Before / after

**Without Golden Boy:** an agent receives "refactor the entire authentication system," starts
immediately, spends aggressively across exploration/implementation/tests, and gets interrupted mid-task
when the budget runs out — with no record of what's done.

**With Golden Boy**, the same request goes through cost estimation and a budget check before execution
scope is committed:

```bash
$ goldenboy plan "Refactor the entire authentication system" --budget 15
--- Execution Plan: 'Refactor the entire authentication system' ---
Remaining Budget: 15.00%
Estimated Cost (heuristic, based on prompt + repo size): 25.37% (confidence: 0.85)
Risk Assessment: LIMITED
```

Risk is assessed *before* work starts, using the real budget and a real cost estimate — not a guess
made after the fact.

## Install

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

The core install has no required third-party dependencies. Optional extras add specific capabilities:

```bash
pip install "goldenboy[tiktoken]"   # exact token counts (falls back to a coarser heuristic without it)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

## Quick start

```bash
goldenboy plan "Refactor the authentication system"   # estimate cost + risk mode before doing anything
goldenboy status                                      # current budget and any pending checkpoint
goldenboy doctor                                      # environment, config, and checkpoint diagnostics
```

## CLI

| Command | Purpose |
|---|---|
| `goldenboy plan <task>` | Estimate a task's real cost from its text + repo size, and show the resulting risk mode. |
| `goldenboy run <task>` | Execute a budget-aware demo plan adaptively against a mock budget. |
| `goldenboy status` | Inspect current budget and any pending checkpoint. |
| `goldenboy resume` | Resume execution from the previous checkpoint. |
| `goldenboy doctor` | Diagnose Python version, optional dependencies, provider key configuration, config, and checkpoint state. |

Add `--budget` to any command to control the mock starting budget, and `-v`/`--verbose` for internal
per-unit decision logs.

## Python integration

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
`goldenboy/__init__.py`; anything not listed there is reachable via its own submodule but isn't part of
the stability contract the top-level API is.

## Integrations

**Provider adapters** report usage; they never execute your code. `MockProvider` is a synthetic provider
for demos and tests. `AnthropicAdapter`/`OpenAIAdapter` read `anthropic-ratelimit-*`/`x-ratelimit-*`
response headers via an explicit `refresh_usage()` call — real work runs through the decorator above,
never inside the adapter:

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

**Claude Code** gets a prompt-level integration instead: `skills/goldenboy/SKILL.md` teaches an LLM
agent to read the `<total_tokens>` figure Claude Code injects directly into context and reason about its
own execution mode — no separate Python process required.

## Architecture

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

## Configuration

Every policy threshold lives in `GoldenBoyConfig`, with this override order:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| Field | Default | Meaning |
|---|---|---|
| `safety_margin` | `3.0` | Percentage points reserved below reported remaining budget before it counts as exhausted. |
| `caution_ratio` | `0.5` | Estimated-cost/usable-budget ratio at which risk moves from SAFE to CAUTION. |
| `base_cost_per_unit` | `2.0` | Fallback per-unit cost when a plan's units don't declare one. |
| `max_budget_tokens` | `100000` | Token count treated as "100% of budget" when converting a raw token estimate into a percentage. |
| `stale_after_seconds` | `300.0` | How long a refreshed provider reading stays `ESTIMATED` before aging to `STALE`. |

Out-of-range values, malformed JSON, and unparseable `GOLDENBOY_*` env vars all raise a clear
`ConfigError` — at the CLI, a one-line `error:` message and exit 1, never a stack trace.

## Design principles

**Lightweight** — the core install has no required third-party runtime dependencies; provider SDKs are
opt-in extras.

**Adaptive** — execution behavior changes with remaining budget *and* with how much to trust that
number: a `STALE` reading can never produce a `SAFE` verdict.

**Deterministic** — identical inputs produce identical decisions. The estimator and risk engine have no
hidden randomness; adapter staleness is driven by an injectable clock, so it's testable without sleeping.

**Provider-optional** — `import goldenboy` never requires `anthropic` or `openai` to be installed.

**Agent-first** — Golden Boy decides how aggressively an agent should proceed based on the remaining
budget. The calling agent remains responsible for understanding and decomposing the task.

**Fail safely** — malformed config, corrupted checkpoints, and invalid input produce a specific,
human-readable error and exit code, never a raw traceback or silent data loss.

## About task breakdowns

The estimated cost shown by `plan`/`run` is computed from the actual task text and repository context —
that number is real. The unit breakdown shown alongside it is illustrative: it is **not** an
LLM-generated decomposition of your task. Golden Boy intentionally keeps its core dependency-free and
out of the business of understanding tasks; actual task decomposition remains the responsibility of the
calling agent (see [Design principles](#design-principles)).

## Limitations

- Cost estimates are heuristic (prompt length + a bounded repo scan) — not billing guarantees, and not a
  model of what an agent would actually load into context.
- Provider usage (rate-limit headers) can change outside Golden Boy's control between refreshes; that's
  exactly what `STALE` confidence exists to flag.
- The `plan`/`run` unit breakdown is illustrative, not task decomposition (see above).
- Golden Boy does not replace the calling coding agent's own judgment — it only informs how much to
  attempt.

## Validation

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

## Roadmap

**v1.0** — done, tested, shipped:

- ✓ Task-aware cost estimation
- ✓ Adaptive execution modes (SAFE/CAUTION/LIMITED/CRITICAL)
- ✓ Checkpoint/defer/resume
- ✓ Usage confidence, including STALE detection
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`)
- ✓ Anthropic/OpenAI provider adapters
- ✓ Claude Code skill integration

**Future** (see `ROADMAP.md` for the full, honest breakdown of Planned vs. Research):

- Additional agent integrations, if a real usage signal exists to build against
- `goldenboy history` (needs a persistence story first)
- Richer benchmarking (large-repo behavior, provider-adapter latency)

Nothing above is claimed production-ready unless it's also covered by tests.

## Development

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

See `CONTRIBUTING.md` for the engineering principles this project holds itself to, `CHANGELOG.md` for
what's changed release to release, and `SECURITY.md` for how credentials are handled and how to report a
vulnerability.

## License

[MIT](LICENSE).

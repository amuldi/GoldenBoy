<p align="center">
  <picture>
    <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy, the budget master">
  </picture>
</p>

<h1 align="center">Golden Boy</h1>

<p align="center">
  <em>Know the budget. Protect the result.</em>
</p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/execution-budget--aware-111111?style=flat-square" alt="Budget Aware">
  <img src="https://img.shields.io/badge/works%20with-any%20agent-111111?style=flat-square" alt="Works with any agent">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <strong>Adaptive execution &middot; recoverable checkpoints &middot; no silent budget overruns</strong><br>
  <sub>For AI coding tasks where agents can run out of quota mid-task. Golden Boy adapts the execution plan to available budget, prioritizing critical features and cleanly deferring optional polish, so a constrained run ends with a usable, working result and a clear record of what's deferred — instead of running out of budget silently mid-edit. See <a href="#limitations">Limitations</a> for what this doesn't guarantee.</sub>
</p>

---

You have 15% usage remaining. You submit a large coding task.

The agent starts normally. It spends the remaining budget on repository exploration, implementation, refactoring, testing, and optional improvements. 

Then the budget runs out before the final result is returned. 

The problem isn't necessarily that the agent couldn't perform the task. The problem is that it failed to **adapt the task to the budget available**.

Golden Boy puts a budget-aware execution layer inside your AI agent.

## Before / after

You ask an agent to rebuild the entire dashboard UI, add responsive support, refactor components, and run the test suite.

Without Golden Boy:

Prompt → Agent starts → Analyze → Implement → Refactor → Test → **Budget exhausted** → Incomplete, broken result.

With Golden Boy:

Prompt → Check budget → Estimate task → Assess risk → Adapt plan → Execute critical work → Validate → Checkpoint → **Return working result**.

> "Core dashboard redesign completed. 3 optional tasks deferred. Checkpoint saved."

## The Result-First Principle

**The rule is never "use fewest tokens."** It is: maximize completed, useful work within the remaining budget.

Golden Boy prefers a smaller completed result over a larger unfinished task. It never allows the agent to spend the remaining budget on low-priority improvements if doing so risks preventing a usable result from being returned.

### What Golden Boy is not

Golden Boy is a budget/workload optimization layer — not a coding agent, chatbot, LLM wrapper, prompt
generator, or IDE. It doesn't decide *what* code to write; it decides *how much* to attempt given what's
left, and helps whatever agent is doing the writing stop safely and recoverably when it can't attempt
everything. Features that would turn it into a general assistant belong in a different project.

## Execution Modes

Golden Boy dynamically assesses risk and switches modes:

1. **SAFE**: Remaining budget is comfortably above estimated task cost. Normal execution.
2. **CAUTION**: Budget is sufficient but execution has some risk. Reduce unnecessary exploration.
3. **LIMITED**: Task is likely to exceed budget. Prioritize critical work, reduce scope, defer secondary work.
4. **CRITICAL**: Budget is almost exhausted. Finish current unit, save checkpoint, stop safely.

## Checkpoints

Large tasks must be recoverable. If the budget becomes unsafe, Golden Boy saves the current state (a checkpoint). The next execution resumes from this checkpoint instead of restarting the entire task unnecessarily.

## Architecture

Golden Boy is designed around a provider-agnostic architecture:
- **Provider Adapters**: Normalize available usage info across providers into a `Budget`, tagged with
  where it came from and how much to trust it (`source` / `UsageConfidence`: EXACT, ESTIMATED, STALE,
  UNKNOWN). Adapters report usage; they do not execute coding work themselves — see
  [Provider adapters vs. real execution](#provider-adapters-vs-real-execution) below.
- **Task Estimator**: Predicts cost from prompt length and repository size (heuristic, not exact —
  see [Limitations](#limitations)).
- **Risk Engine**: Determines Execution Mode (SAFE/CAUTION/LIMITED/CRITICAL) from a `GoldenBoyConfig`
  rather than hardcoded thresholds — see `goldenboy/core/config.py`.
- **Adaptive Executor**: Executes and checkpoints based on priority. `AdaptiveExecutor.assess(plan)` is
  the single decision path shared by the CLI and the `budget_aware_execution` decorator.

## Provider adapters vs. real execution

Golden Boy does not execute coding work itself — that would make it a coding agent, which is explicitly
not its job (see [What Golden Boy is not](#what-golden-boy-is-not) above). There are two adapter styles:

- **`MockProvider`** genuinely can execute a unit (it just deducts the unit's cost from a counter), which
  is why it's used by the CLI demo and by `AdaptiveExecutor.execute()`.
- **`AnthropicAdapter` / `OpenAIAdapter`** only report usage, by reading `anthropic-ratelimit-*` /
  `x-ratelimit-*` response headers from a minimal probe call (`refresh_usage()`). They do not implement
  `execute_unit` — calling it raises `NotImplementedError` with a pointer to the right pattern. For real
  work with these adapters, wrap your own function:

```python
from goldenboy.adapters.anthropic_adapter import AnthropicAdapter
from goldenboy.integration import budget_aware_execution
from goldenboy.core.priorities import Priority

adapter = AnthropicAdapter()
adapter.refresh_usage()  # optional: refresh the cached usage estimate first

@budget_aware_execution(adapter, "1", "Refactor auth module", Priority.P1)
def refactor_auth():
    ...  # your actual agent logic runs here, never inside the adapter
```

## Claude Code integration

`skills/goldenboy/SKILL.md` is a prompt-level integration: it teaches an LLM agent to reason about its
own remaining budget rather than asking Golden Boy's Python layer to track it externally. In Claude Code
specifically, the harness injects the remaining-usage figure directly into context, e.g.:

```
<system-reminder>
<total_tokens>15000000 tokens left</total_tokens>
</system-reminder>
```

The skill instructs the agent to read that value directly rather than guess. This is currently the
primary Claude Code integration; the Python `ProviderAdapter` layer is a separate, code-level mechanism
for frameworks that call the OpenAI/Anthropic APIs directly and want programmatic budget checks.

## Install

Golden Boy's core package has no required dependencies beyond the standard library.

```bash
pip install -e .
```

Install extras only for what you actually use:

```bash
pip install -e ".[tiktoken]"    # exact token counts (falls back to a word-count heuristic without it)
pip install -e ".[anthropic]"   # AnthropicAdapter
pip install -e ".[openai]"      # OpenAIAdapter
pip install -e ".[dev]"         # pytest + ruff + mypy, for contributing
```

See `.env.example` for the environment variables the adapters read.

## Quick start

```bash
pip install -e .
goldenboy plan "Fix a typo in README" --budget 50
goldenboy plan "Build an OAuth authentication system with tests" --budget 50
```

The two `plan` calls print different `Estimated Cost` values — that's the real, task-text-driven
estimate (see [Limitations](#limitations) for what it doesn't do: it estimates cost, it doesn't
decompose the task into a real plan). Try a low budget to see modes change:

```bash
goldenboy run "demo" --budget 12       # some units complete, some get deferred
goldenboy status --budget 12           # shows the checkpoint left behind
goldenboy resume --budget 100          # finishes the deferred work
goldenboy doctor                       # environment/config/checkpoint diagnostics
```

## Python integration

The public API is small and doesn't require any provider SDK:

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # your real work goes here — Golden Boy decides whether to call it at all

refactor_auth()
```

`budget_aware_execution` asks the provider for a budget/mode decision and, only if the mode allows it,
calls your function — never the provider. See `goldenboy/__init__.py` for the full public surface;
anything not listed there (provider-specific adapters, CLI internals) is available via its own submodule
but isn't part of the stability contract the top-level API is.

## Configuration

Every policy threshold lives in one place, `GoldenBoyConfig`, with this override order:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| Field | Default | Meaning |
|---|---|---|
| `safety_margin` | `3.0` | Percentage points reserved below reported remaining budget before it counts as exhausted. |
| `caution_ratio` | `0.5` | Estimated-cost/usable-budget ratio at which risk moves from SAFE to CAUTION. |
| `base_cost_per_unit` | `2.0` | Fallback per-unit cost when a plan's units don't declare one. |
| `max_budget_tokens` | `100000` | Token count treated as "100% of budget" when converting a raw token estimate into a percentage. |
| `stale_after_seconds` | `300.0` | How long a refreshed `AnthropicAdapter`/`OpenAIAdapter` reading stays `ESTIMATED` before aging to `STALE` (see [Safety model](#safety-model)). |

Example `.goldenboy/config.json`:

```json
{
  "safety_margin": 5.0,
  "caution_ratio": 0.4
}
```

Out-of-range values (e.g. `caution_ratio` outside `[0, 1]`), malformed JSON, and unparseable
`GOLDENBOY_*` env vars all raise a clear `ConfigError` — at the CLI they print a one-line `error:` message
and exit 1, not a stack trace. Unknown keys in the JSON file are ignored with a logged warning (helps
catch typos without hard-failing on a file written for a slightly older version).

## Commands

Use the CLI to interact with Golden Boy's execution layer:

| Command | What it does |
|---------|--------------|
| `goldenboy status` | Show remaining budget, usable budget (after safety margin), and any pending checkpoint (with its saved-at time and next recommended action). |
| `goldenboy plan <task>` | Estimate `<task>`'s real cost (from prompt length + repo size) and show the resulting risk mode, alongside an illustrative example unit breakdown. |
| `goldenboy run <task>` | Execute the illustrative example plan adaptively against a mock budget — a demo of mode-based adaptation, not a decomposition of `<task>`. |
| `goldenboy resume` | Resume execution from the previous checkpoint. |
| `goldenboy doctor` | Report Python version, which optional dependencies are installed (and whether their API key is configured — never its value), whether config loads cleanly, and any checkpoint state — real, checked facts, not a fabricated health score. |

*(Note: Provide a `--budget` flag to mock available quota during testing, and `-v`/`--verbose` to see
internal per-unit decision logs.)*

## Safety model

Golden Boy's "safety" is about not losing work or silently doing the wrong thing, not sandboxing —
it never executes arbitrary code you didn't write (see [Provider adapters vs. real
execution](#provider-adapters-vs-real-execution)):

- **Config never fails silently.** Out-of-range thresholds, malformed JSON, and bad env var values all
  raise `ConfigError` with a specific reason — Golden Boy never falls back to a default that could mask
  a threshold you intentionally tightened.
- **Checkpoints never fail silently either.** A corrupted or incompatible-version checkpoint raises
  `CheckpointError` naming the file and the problem, instead of crashing with a raw traceback or quietly
  discarding deferred work.
- **CRITICAL mode stops, it doesn't guess.** When budget is at/below the safety margin, execution defers
  everything except P0 and writes a checkpoint — it does not attempt partial work "just in case" the
  estimate was wrong.
- **Old usage data doesn't get to look fresh.** `AnthropicAdapter`/`OpenAIAdapter` track when they were
  last refreshed; once a reading is older than `stale_after_seconds`, its confidence becomes `STALE`
  (not `ESTIMATED`), and `RiskEngine` will not report `SAFE` on a `STALE` budget — at best `CAUTION` —
  even if the numbers alone would otherwise look comfortable. A long-running process that fetched usage
  once and never refreshed again can't silently coast on that first reading forever.
- **Nothing is logged that shouldn't be.** API keys are read from the environment and never appear in
  checkpoint files, logs, error messages, or `goldenboy doctor` output — `doctor` reports only whether a
  key is configured (e.g. `Anthropic API key: configured`), never its value (see `SECURITY.md`).

## Limitations

- **Estimation is heuristic, not exact.** `Estimator` predicts cost from prompt length and a bounded
  scan of source files (dependency/build directories excluded) — it doesn't model what an agent would
  actually load into context for a given task.
- **No automatic task decomposition.** `plan`/`run` don't turn your task text into real `ExecutionUnit`s
  — the CLI's example plan is fixed and illustrative (see [Provider adapters vs. real
  execution](#provider-adapters-vs-real-execution)). Define your own units for a real plan, or use the
  SKILL.md prompt-level approach for an LLM agent to reason about its own decomposition.
- **Rate-limit headers ≠ session budget.** `AnthropicAdapter`/`OpenAIAdapter` report an org-wide
  rate-limit bucket, not "how much of this coding session is left" — that's why their `Budget` is never
  EXACT: UNKNOWN before the first refresh, ESTIMATED while fresh, STALE once older than
  `stale_after_seconds`.
- **No guarantees.** Golden Boy cannot guarantee a task finishes within budget, but it fails safely
  (CRITICAL mode, checkpoint written) when budget information is unavailable or exhausted, rather than
  silently continuing.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ --cov=goldenboy --cov-report=term-missing
ruff check goldenboy tests scripts run_tests.py
mypy
```

mypy fails CI on any type error; coverage is reported but has no enforced threshold — the goal is
confidence, not a number to chase (see `.github/workflows/ci.yml`). See `scripts/benchmark.py` /
`BENCHMARKS.md` for real (not fabricated) latency numbers, `CONTRIBUTING.md` for the engineering
principles this project holds itself to, `ROADMAP.md` for what's done vs. planned vs. still research, and
`CHANGELOG.md` for what's changed release to release.

## Security

See `SECURITY.md` for what Golden Boy persists, how credentials are handled, and how to report a
vulnerability privately.

## Roadmap

`ROADMAP.md` tracks what's Done, In Progress, Planned, or Research — including explicit non-goals (e.g.
Golden Boy executing code itself is a non-goal, not a "planned" feature). Nothing there is claimed
production-ready unless it's also covered by tests.

## Contributing

See `CONTRIBUTING.md` for setup, the checks a PR needs to pass (`pytest`, `ruff`, `mypy`, `python -m
build`), and the engineering principles this project holds itself to — chiefly: change the smallest
correct thing, never fabricate functionality to make something look finished, and never present an
estimate or heuristic as if it were exact.

## License

[MIT](LICENSE). The shortest license that works.

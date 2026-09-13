# Contributing to Golden Boy

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

`.[dev]` installs `pytest` and `ruff` but not the `anthropic`/`openai`
extras — you don't need real API keys to work on the core library, CLI, or
tests. Install `.[anthropic]` and/or `.[openai]` only if you're changing
one of those adapters.

## Running checks

```bash
pytest tests/            # unit tests
ruff check goldenboy tests scripts   # lint
mypy                                 # type check
python -m build           # packaging sanity check
```

All three run in CI (see `.github/workflows/ci.yml`) and are expected to
pass before a PR merges.

## What belongs in this project

Golden Boy is a budget/workload optimization layer for AI coding agents —
see the "Critical rule" in the README. Before adding a feature, check that
it reinforces that identity rather than growing Golden Boy into a general
coding assistant, chatbot, or LLM wrapper. If in doubt, open an issue to
discuss scope before writing code.

## Engineering principles

These guide review, in rough priority order:

1. **Existing architecture first** — don't rewrite a working module to
   match a preference; change it when it's actually blocking correctness,
   testability, or clarity.
2. **Root cause over symptom** — if a fix only makes a specific test pass,
   look one level up for why the bug was possible.
3. **No fake completeness** — a feature that looks done in the CLI/README
   but doesn't do what it claims is worse than not having it. Label
   demos/examples as such (see `create_example_plan` in `cli.py` for the
   pattern).
4. **Honest confidence** — anything derived from an estimate, heuristic, or
   proxy signal (see `UsageConfidence` in `goldenboy/core/budget.py`) must
   say so; never present ESTIMATED/UNKNOWN data as EXACT.
5. **No hardcoded policy numbers** — thresholds belong in
   `goldenboy/core/config.py`, not scattered as default arguments.

## Tests

New behavior needs a test. Bug fixes should include a regression test that
fails on the old code (see `tests/test_estimator.py` for an example that
reproduces a real bug before fixing it). Boundary conditions on
budget/risk thresholds are worth testing explicitly — see
`tests/test_risk_boundaries.py`.

## Commit style

Plain, descriptive commit messages. No required prefix convention yet.

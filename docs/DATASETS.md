# Dataset & Research Landscape

Desk research into public datasets/research relevant to AI coding agents and
software engineering, done before building `goldenboy.replay`/`goldenboy.analytics`
(2026-09-14). This is **research notes, not an integration list** — Golden
Boy does not bundle, download, or depend on any dataset described here. It
exists so the reasoning behind `goldenboy replay`'s design (operate on
Golden Boy's own local `HistoryStore`, never a synthetic or borrowed
dataset) is written down and checkable, per the project's "no fabricated
historical datasets" rule.

## Why none of these are used as Golden Boy's own data source

Every dataset below evaluates **code-generation correctness** (did the
patch pass the tests?) on a fixed task set. None of them record what
Golden Boy actually needs to backtest a resource-allocation policy: a
sequence of *(remaining budget before, estimated cost, decision made,
budget after, outcome)* tuples for real agent sessions operating under a
real, shrinking usage budget. That data only exists once Golden Boy (or
something like it) has been run for real — which is exactly what
`HistoryStore` (`.goldenboy/history.jsonl`) starts collecting from the
first `budget_aware_execution` call. See `goldenboy/replay/engine.py`'s
module docstring and [`goldenboy replay`](../README.md#-cli-reference)'s
honest `N/A` output on a fresh install.

Where these datasets *are* directly useful: validating `TaskClassifier`
(`goldenboy/core/task_classifier.py`) against real, human-written GitHub
issue text, and — for SWE-bench specifically — as a future source of
realistic repository sizes/prompt lengths to sanity-check `Estimator`
against. Neither integration exists yet; both are listed as research
starting points below, not shipped features.

---

## SWE-bench / SWE-bench Verified

| | |
|---|---|
| **Source** | [princeton-nlp/SWE-bench](https://github.com/swebench/SWE-bench) (original); [SWE-bench/SWE-bench_Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) (OpenAI-collaborated, human-filtered subset) |
| **License** | The SWE-bench *codebase* is MIT-licensed. The dataset content (GitHub issue text, patches) is derived from public repositories and inherits each source repository's own license/terms — SWE-bench does not re-license the underlying issue/PR text under a single blanket license. |
| **Size** | Original: 2,294 task instances across 12 popular Python repositories. Verified: 500 instances, human-filtered by professional software engineers (with OpenAI) for clear problem statements and reliable tests. |
| **Task type** | Real GitHub issue → resolve it with a patch; a `FAIL_TO_PASS`/`PASS_TO_PASS` test suite verifies the patch. |
| **Features** | `problem_statement` (issue text), `base_commit`, `patch` (gold fix), `test_patch`, `hints_text` (pre-PR discussion), `repo`, `created_at`, `version`. |
| **Target** | Binary: does the generated patch make `FAIL_TO_PASS` tests pass and `PASS_TO_PASS` tests keep passing? |
| **Limitations** | Python-only, 12 repositories (not representative of arbitrary codebases); no resource/usage/budget data at all — it measures correctness, not cost or decision quality. |
| **Relevance to Golden Boy** | Real, human-written issue text is a good future source for validating `TaskClassifier`'s BUG_FIX/IMPLEMENTATION/ARCHITECTURE_CHANGE calls against ground truth (the issue's actual resolution category). Not usable for the replay/backtest questions in `goldenboy.replay` — no budget or decision data exists in it. |

## HumanEval

| | |
|---|---|
| **Source** | [openai/openai_humaneval](https://huggingface.co/datasets/openai/openai_humaneval) (OpenAI, 2021) |
| **License** | MIT |
| **Size** | 164 hand-written Python problems, ~7.7 unit tests each. |
| **Task type** | Function-level code generation from a docstring. |
| **Features** | Function signature, docstring (natural-language spec), reference solution, unit tests. |
| **Target** | pass@k: does the generated function body pass all unit tests? |
| **Limitations** | Small, single-function scope (not repository-level); widely used as an LLM training/eval target, so contamination risk is high for any model trained after ~2022. |
| **Relevance to Golden Boy** | Low. Single-function tasks have no analog to "remaining agent budget across a multi-step session" — useful only as a sanity check that `Estimator`'s prompt-token counting behaves reasonably on short, well-defined prompts. |

## LiveCodeBench

| | |
|---|---|
| **Source** | [livecodebench/livecodebench](https://github.com/livecodebench/livecodebench) |
| **License** | MIT (the benchmark codebase); problems are sourced from LeetCode, AtCoder, and CodeForces and carry those platforms' own terms for the problem statements themselves. |
| **Size** | Growing, time-versioned releases: 400 problems (`release_v1`, May 2023–Mar 2024) up to 1,055 problems (`release_v6`, May 2023–Apr 2025). |
| **Task type** | Competitive-programming problem → generate a correct solution. |
| **Features** | Problem statement, release/contest date (used for contamination control), test cases (a "lite" pruned set is the default; `--not_fast` unlocks the full set). |
| **Target** | pass@1 / pass@5 against held-out test cases. |
| **Limitations** | Competitive-programming style problems are not representative of typical software-engineering maintenance work (the bulk of what `TaskType` in `goldenboy.core.task_types` is meant to cover — bug fixes, refactors, dependency bumps, etc.). |
| **Relevance to Golden Boy** | Low-to-none directly. Its contamination-control methodology (time-windowed releases) is a good pattern reference for `goldenboy.replay.engine.walk_forward_folds` — both exist to stop a model from being evaluated on data it could have "seen." |

## RepoBench

| | |
|---|---|
| **Source** | [RepoBench (ICLR 2024)](https://arxiv.org/pdf/2306.03091) |
| **License** | Built from public, permissively-licensed GitHub repositories (Python and Java); check the specific repo's license before reuse of any individual file. |
| **Size** | ~10,345 Python and ~14,956 Java repositories as a training/context pool; 1,075 Python and 594 Java held-out repositories for evaluation. |
| **Task type** | Repository-level code *completion* (not issue resolution) — three sub-tasks: retrieval (RepoBench-R), completion (RepoBench-C), and a combined pipeline (RepoBench-P). |
| **Features** | Cross-file code context, target completion line/block. |
| **Target** | Exact-match / edit-similarity of the completed code. |
| **Limitations** | Measures code completion, not task-level resource consumption or agent decisions; not directly about task success/failure at all. |
| **Relevance to Golden Boy** | Its repository-size distribution is a plausible future input for stress-testing `Estimator._estimate_codebase_context`'s `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` caps against realistically large repos (see `ROADMAP.md`: "Benchmarking behavior against a deliberately large synthetic repository" is listed Planned, not done). No use for replay/backtesting decisions. |

## Published research on agent token consumption

**["How Do AI Agents Spend Your Money? Analyzing and Predicting Token
Consumption in Agentic Coding Tasks"](https://arxiv.org/pdf/2604.22750)**
(2026) is the most directly relevant paper found: it builds a dataset of
token consumption across agentic coding tasks (drawing on SWE-bench/SWE-bench
Verified and a Code-Feedback/ShareGPT-derived corpus), analyzes input/output
token counts and cost per task, and develops models to *predict* token
consumption — the same problem `goldenboy.core.estimator.Estimator` solves
heuristically today. The paper is released under a Creative Commons
Attribution 4.0 license with an accompanying project site
(`longjubai.github.io/agent_token_consumption/`).

**Relevance to Golden Boy:** this is the closest published work to
Golden Boy's own cost-estimation problem, and the natural next research
step if `Estimator` is ever upgraded from a heuristic to a learned model —
but its dataset was not built to answer Golden Boy's specific question
(given a *partially-spent, shrinking* budget and a task-in-progress,
should the agent continue, reduce scope, or stop?). It measures total
consumption per completed task, not budget-aware decisions mid-task.
Nothing from it is integrated into this codebase; it is noted here as the
most relevant prior art, not as a data source.

## Public LLM pricing / rate-limit information

Provider-published pricing pages (e.g. Anthropic's and OpenAI's own
pricing documentation) are the authoritative source for per-token cost,
and change independently of this project — Golden Boy deliberately does
not hardcode dollar-per-token figures anywhere in `goldenboy/core/` for
exactly that reason (`GoldenBoyConfig.max_budget_tokens` is a
normalization constant, not a cost figure; see its docstring). The
`AnthropicAdapter`/`OpenAIAdapter` read live rate-limit *headers*
(`anthropic-ratelimit-tokens-remaining`/`-limit`,
`x-ratelimit-remaining-tokens`/`-limit-tokens`) instead of consulting a
static pricing table, so this project's own numbers can't go stale the
way a hardcoded price table would.

## Open-source agent telemetry tooling

A search for prior art in this space surfaced community dashboards (e.g.
"TokenTelemetry"-style local observability tools that parse coding-agent
session logs for token/tool-call counts) and the broader move toward
OpenTelemetry semantic conventions for LLM/agent spans
(`gen_ai.request.model`, `gen_ai.system`, etc.). None were adopted:
Golden Boy's own `HistoryStore`/`TaskEvent` schema
(`goldenboy/core/history.py`) is deliberately smaller and scoped to
exactly the fields the decision/replay layers need, consistent with "no
unnecessary dependencies / no unnecessary frameworks." Adopting a full
OpenTelemetry pipeline for a local-first, dependency-free CLI tool would
be a disproportionate amount of new surface area for the problem at hand
— revisit only if a concrete integration need (e.g. exporting Golden
Boy's own events into an existing observability stack) actually arises.

---

## Conclusion

No dataset surveyed here is a drop-in substitute for Golden Boy's own
event log. The correct, honest next step — already built — is
`HistoryStore` collecting real local data from actual use, with
`goldenboy.replay`/`goldenboy.analytics` reporting `N/A`/`NO_DATA` until
enough of it exists (see [`goldenboy validate`](../README.md#-cli-reference)).
This document should be revisited once real historical data accumulates,
to decide whether any of the above remain useful as an external
cross-check rather than a primary data source.

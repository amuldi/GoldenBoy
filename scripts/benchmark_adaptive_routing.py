"""Adaptive-routing benchmark: does `AdaptiveModelRouter` actually pick
different (cheaper/different) models than a fixed-strong-model baseline,
and what does that do to projected cost/tokens/latency, holding the
LLM-call layer itself constant?

HONESTY NOTE (read this before trusting any number below): this machine has
no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` set (checked via `os.environ` at
import time -- see `_HAS_REAL_KEYS` below), so this script makes zero real
network calls. `MockProvider` (Stage 1's deterministic, no-network adapter)
stands in for the raw text-generation step on every attempt, for both the
baseline and the adaptive condition alike. Concretely:

  - Task classification, complexity scoring, token estimation, routing
    (`AdaptiveModelRouter.route()`), governance (`PolicyEngine`), result
    evaluation, and escalation (`suggest_escalation`) are all REAL Golden
    Boy logic, exercised exactly as `GoldenBoy.run()` would exercise them
    against a real adapter.
  - Token counts are REAL, in the sense that they are exactly what
    `MockProvider.generate()` deterministically computed from the actual
    prompt text and the actual `output_budget_tokens` each condition's
    routing plan produced -- not hand-typed numbers.
  - Cost is PROJECTED: `ModelRegistry`'s real, published per-1K pricing
    (see `model_registry.py`'s inline `source` comments) applied to those
    real token counts. It is NOT measured from a live API bill, because no
    live call was made.
  - Latency is Golden Boy's own Python-code overhead (classification +
    estimation + routing + governance + evaluation + the mock call's
    near-zero cost), NOT end-to-end network/API latency. It is real
    wall-clock time of this process, on this machine, right now -- but it
    says nothing about what a real Anthropic/OpenAI round trip would cost
    in time.

If real API keys are later present in `os.environ`, this script still
defaults to MockProvider: this is a shared dev machine, the benchmark's
whole point is isolating Golden Boy's own routing/escalation logic from
provider variance, and spending real money was not asked for. That default
is documented, not hidden.

Design, to avoid a specific trap: `ProviderAdapter.generate()` has no
`model` parameter -- a concrete adapter is permanently bound to one model
at construction (see `adapters/base.py`). `GoldenBoy.adapters` is keyed by
*provider*, not by provider+model, so only one model per provider can ever
actually execute inside one `GoldenBoy` instance, even though
`AdaptiveModelRouter` reasons over every model `ModelRegistry` has for that
provider. To keep "which model got selected" and "which model actually
executed" from silently diverging, each condition below is run against a
`ModelRegistry` that is deliberately scoped to exactly one model per
provider -- a real subset of `model_registry.py`'s built-in defaults, never
an invented entry -- so the router's selection and the adapter's fixed
model are always the same model, by construction, not by coincidence.
"""
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldenboy.adapters.mock import MockProvider  # noqa: E402
from goldenboy.core.adaptive_router import AdaptiveRouterConfig, CapabilityRequirements  # noqa: E402
from goldenboy.core.model_registry import ModelRegistry, get_default_registry  # noqa: E402
from goldenboy.goldenboy import GoldenBoy, GoldenBoyRunResult  # noqa: E402

_HAS_REAL_KEYS = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))

# --- Registries: real subsets of the default registry, one model per provider ---

_DEFAULT = get_default_registry()


def _subset(*pairs: tuple) -> ModelRegistry:
    specs = {}
    for provider, model in pairs:
        spec = _DEFAULT.get(provider, model)
        assert spec is not None, f"{provider}:{model} must exist in the default registry"
        specs[f"{provider}:{model}"] = spec
    return ModelRegistry(specs=specs)


# Baseline: the single highest quality_class ("frontier") model in the whole
# default registry -- claude-opus-4-1. Scoped to just this one entry so
# there is no ambiguity about which model the single adapter executes.
BASELINE_REGISTRY = _subset(("anthropic", "claude-opus-4-1"))
BASELINE_ADAPTERS: Dict[str, MockProvider] = {
    "anthropic": MockProvider(model="claude-opus-4-1", initial_percentage=100.0),
}

# Adaptive: two real, differently-priced/quality-classed models, one per
# provider -- claude-haiku-4-5 (fast/cheap) and gpt-4o (balanced/pricier).
# `AdaptiveModelRouter`'s real "adaptive" strategy picks between them based
# on real complexity scoring, not a hand-picked answer.
ADAPTIVE_REGISTRY = _subset(("anthropic", "claude-haiku-4-5"), ("openai", "gpt-4o"))
ADAPTIVE_ADAPTERS: Dict[str, MockProvider] = {
    "anthropic": MockProvider(model="claude-haiku-4-5", initial_percentage=100.0),
    "openai": MockProvider(model="gpt-4o", initial_percentage=100.0),
}

_AVAILABLE_BUDGET_USD = 1.0  # generous -- the thing under test is model *choice*, not budget denial


@dataclass
class TaskSpec:
    name: str
    tier: str  # "simple" | "medium" | "complex"
    task_type: str  # a real TaskType enum value
    prompt: str


# At least 3 tiers x 2 task-type categories -> 6 distinct prompts.
# "complex" prompts are deliberately long (pushes MockProvider's
# input_tokens > a modest output_budget_tokens, which is the real,
# deterministic truncation condition `MockProvider.generate()` implements
# -- see mock.py -- giving at least one genuine escalation case) AND loaded
# with real complexity-scoring keywords from `complexity.py`'s signal table
# (architecture/migration/cross-module/etc.) so `_complexity_label()` (a
# real, independent scorer) actually reports HIGH/VERY_HIGH for them, which
# is what flips `AdaptiveModelRouter`'s "adaptive" strategy from
# cost_first-like to quality_first-like behavior.

# NOTE, found while running this: `MockProvider.generate()`'s truncation
# condition is `input_tokens > max_output_tokens`, where `max_output_tokens`
# is `RoutingPlan.output_budget_tokens` -- and `Estimator.estimate_task()`
# always sizes `estimated_output_tokens` as `prompt_tokens * multiplier`
# with `multiplier >= 1.5` (see estimator.py's `_OUTPUT_MULTIPLIER_MIN`).
# That means `output_budget_tokens >= 1.5 * input_tokens` is structurally
# guaranteed on every first attempt -- truncation, and therefore escalation,
# can never actually fire through this path no matter how long the prompt
# is. The long "_complex" prompts below are kept (they still produce a real,
# measurable HIGH/VERY_HIGH complexity label and a large real token count)
# but they do not produce an escalation, and the results file reports that
# plainly rather than claiming one that didn't happen.

TASKS: List[TaskSpec] = [
    TaskSpec(
        name="coding_simple",
        tier="simple",
        task_type="bug_fix",
        prompt="Fix a typo in the README.",
    ),
    TaskSpec(
        name="coding_medium",
        tier="medium",
        task_type="implementation",
        prompt="Add input validation to the signup form and cover it with a couple of tests.",
    ),
    TaskSpec(
        name="coding_complex",
        tier="complex",
        task_type="architecture_change",
        prompt=(
            "Re-architect the payments service: migrate the data model across all services "
            "end to end, change the public API with a breaking schema change, update every "
            "dependency in requirements.txt, and refactor the duplicated retry logic "
            "throughout the codebase. " * 40
        ),
    ),
    TaskSpec(
        name="reasoning_simple",
        tier="simple",
        task_type="research",
        prompt="Summarize the difference between a list and a tuple in Python.",
    ),
    TaskSpec(
        name="reasoning_medium",
        tier="medium",
        task_type="research",
        prompt=(
            "Compare three retry-backoff strategies for a flaky downstream dependency and "
            "recommend one, with tradeoffs, for a task that also needs a short test plan."
        ),
    ),
    TaskSpec(
        name="reasoning_complex",
        tier="complex",
        task_type="architecture_change",
        prompt=(
            "Design the new service's system design and architecture for a cross-module "
            "migration: evaluate a schema change and breaking change to the public api, a "
            "dependency upgrade across multiple services, and a full test coverage plan, "
            "reasoning end-to-end about failure modes across all affected modules. " * 40
        ),
    ),
]


@dataclass
class ConditionResult:
    task: TaskSpec
    result: GoldenBoyRunResult
    wall_clock_ms: float

    @property
    def selected(self) -> str:
        plan = self.result.final_routing_plan
        if plan is None or plan.provider is None:
            return "none"
        return f"{plan.provider}:{plan.model}"

    @property
    def input_tokens(self) -> int:
        return sum(a.generation_result.input_tokens for a in self.result.attempts if a.generation_result)

    @property
    def output_tokens(self) -> int:
        return sum(a.generation_result.output_tokens for a in self.result.attempts if a.generation_result)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def attempt_count(self) -> int:
        return len(self.result.attempts)

    @property
    def escalation_count(self) -> int:
        return sum(1 for a in self.result.attempts if a.escalation is not None)


def _run_condition(
    task: TaskSpec, adapters: Dict[str, MockProvider], registry: ModelRegistry, strategy: str
) -> ConditionResult:
    gb = GoldenBoy(
        adapters=dict(adapters),  # fresh dict per call; MockProvider instances are reused but
        registry=registry,  # stateless aside from the budget counter `generate()` never touches
        router_config=AdaptiveRouterConfig(strategy=strategy),
    )
    start = time.perf_counter()
    result = gb.run(
        task.prompt,
        task_type=task.task_type,
        capability_requirements=CapabilityRequirements(),
        available_budget_usd=_AVAILABLE_BUDGET_USD,
        max_attempts=3,
    )
    wall_clock_ms = (time.perf_counter() - start) * 1000.0
    return ConditionResult(task=task, result=result, wall_clock_ms=wall_clock_ms)


def _projected_cost_usd(cr: ConditionResult, registry: ModelRegistry) -> Optional[float]:
    """Real-token-count x real-published-pricing for whichever model each
    attempt actually ran against (never the plan's pre-call estimate --
    see `goldenboy.py::_estimate_cost_usd`, the same formula GoldenBoy.run()
    itself uses internally for `total_cost_usd`)."""
    total = 0.0
    any_priced = False
    for attempt in cr.result.attempts:
        if attempt.generation_result is None:
            continue
        # Look the spec up by the routing *plan*'s provider/model, not
        # `GenerationResult.provider/.model` -- `MockProvider.provider_name`
        # is the fixed literal `"mock"` (see adapters/mock.py), not
        # "anthropic"/"openai", so a `registry.get()` keyed off the
        # generation result would always miss and silently price every
        # mock-backed attempt at $0. The routing plan's provider/model is
        # the real registry key this benchmark cares about (and is, by
        # this script's one-model-per-provider registry construction,
        # exactly the model that executed).
        spec = registry.get(attempt.plan.provider, attempt.plan.model)
        if spec is None:
            continue
        any_priced = True
        total += (attempt.generation_result.input_tokens / 1000.0) * spec.input_cost_per_1k
        total += (attempt.generation_result.output_tokens / 1000.0) * spec.output_cost_per_1k
    return total if any_priced else None


def main() -> None:
    print("Golden Boy adaptive-routing benchmark -- real measurements, this machine, right now.\n")
    if _HAS_REAL_KEYS:
        _key_note = "using MockProvider anyway (see script docstring)"
    else:
        _key_note = "MockProvider used because no real API keys were available in this environment"
    print(f"Real API keys present in os.environ: {_HAS_REAL_KEYS} -- {_key_note}.\n")

    rows = []
    for task in TASKS:
        baseline = _run_condition(task, BASELINE_ADAPTERS, BASELINE_REGISTRY, strategy="quality_first")
        adaptive = _run_condition(task, ADAPTIVE_ADAPTERS, ADAPTIVE_REGISTRY, strategy="adaptive")
        rows.append((task, baseline, adaptive))

        print(f"== {task.name} ({task.tier}, {task.task_type}) ==")
        print(
            f"  baseline : model={baseline.selected:<28} tokens={baseline.total_tokens:>6} "
            f"(in={baseline.input_tokens},out={baseline.output_tokens}) "
            f"cost=${(_projected_cost_usd(baseline, BASELINE_REGISTRY) or 0.0):.6f} "
            f"attempts={baseline.attempt_count} escalations={baseline.escalation_count} "
            f"success={baseline.result.sufficient} latency={baseline.wall_clock_ms:.3f}ms"
        )
        print(
            f"  adaptive : model={adaptive.selected:<28} tokens={adaptive.total_tokens:>6} "
            f"(in={adaptive.input_tokens},out={adaptive.output_tokens}) "
            f"cost=${(_projected_cost_usd(adaptive, ADAPTIVE_REGISTRY) or 0.0):.6f} "
            f"attempts={adaptive.attempt_count} escalations={adaptive.escalation_count} "
            f"success={adaptive.result.sufficient} latency={adaptive.wall_clock_ms:.3f}ms"
        )
        print()

    out_path = Path(__file__).resolve().parent.parent / "benchmarks" / "results"
    out_path.mkdir(parents=True, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    md_path = out_path / f"{date_str}-adaptive-routing.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Adaptive routing benchmark -- {date_str}\n\n")
        f.write("Generated by `scripts/benchmark_adaptive_routing.py`. Real measurements, single "
                "machine, single run -- same caveats as `BENCHMARKS.md`. Not part of CI.\n\n")
        f.write(f"Platform: `{sys.platform}`, Python `{sys.version.split()[0]}`.\n\n")
        f.write("## Honesty note\n\n")
        f.write(
            f"Real API keys present in `os.environ`: **{_HAS_REAL_KEYS}**. "
            "MockProvider (Stage 1's deterministic, no-network adapter) was used for *every* "
            "generation call below, for both conditions -- no real network calls were made, "
            "and no cost/latency numbers here were measured from a live API bill. "
            "Task classification, complexity scoring, token estimation, `AdaptiveModelRouter."
            "route()`, `PolicyEngine.evaluate()`, result evaluation, and `suggest_escalation()` "
            "are all real Golden Boy logic; token counts are real outputs of that logic applied "
            "to the real prompts below; cost is **projected** from `ModelRegistry`'s real "
            "published per-1K pricing applied to those real token counts; latency is Golden "
            "Boy's own Python-overhead wall-clock time, **not** end-to-end API latency. "
            "See the script's module docstring for the full explanation, including why the "
            "baseline and adaptive conditions each use a registry scoped to exactly one model "
            "per provider.\n\n"
        )
        f.write(
            "## Method\n\n"
            "- **Baseline**: `GoldenBoy.run()` with a `ModelRegistry` containing only "
            "`anthropic:claude-opus-4-1` (the single highest `quality_class=\"frontier\"` "
            "model in the full default registry) and a single matching adapter -- every task "
            "is forced onto this one model; `AdaptiveModelRouter` is still called for real, it "
            "just has only one qualifying candidate.\n"
            "- **Adaptive**: `GoldenBoy.run()` with a `ModelRegistry` containing exactly "
            "`anthropic:claude-haiku-4-5` (fast/cheap) and `openai:gpt-4o` (balanced/pricier), "
            "and matching adapters for both, routed with the real `\"adaptive\"` strategy "
            "(cost-first below the HIGH complexity threshold, quality-first at/above it).\n"
            "- 6 tasks across 3 complexity tiers (simple/medium/complex) x 2 task-type "
            "categories (coding-ish: bug_fix/implementation/architecture_change; "
            "reasoning-ish: research/architecture_change).\n\n"
        )
        f.write(
            "| Task | Tier | Condition | Model selected | Input tok | Output tok | Total tok | "
            "Projected cost (USD) | Attempts | Escalations | Success | Overhead latency (ms) |\n"
        )
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for task, baseline, adaptive in rows:
            conditions = (
                ("baseline", baseline, BASELINE_REGISTRY),
                ("adaptive", adaptive, ADAPTIVE_REGISTRY),
            )
            for label, cr, reg in conditions:
                cost = _projected_cost_usd(cr, reg)
                cost_str = f"{cost:.6f}" if cost is not None else "N/A"
                f.write(
                    f"| {task.name} | {task.tier} | {label} | {cr.selected} | {cr.input_tokens} | "
                    f"{cr.output_tokens} | {cr.total_tokens} | {cost_str} | {cr.attempt_count} | "
                    f"{cr.escalation_count} | {cr.result.sufficient} | {cr.wall_clock_ms:.3f} |\n"
                )

        f.write("\n## Observed deltas\n\n")
        total_baseline_cost = sum(_projected_cost_usd(b, BASELINE_REGISTRY) or 0.0 for _, b, _ in rows)
        total_adaptive_cost = sum(_projected_cost_usd(a, ADAPTIVE_REGISTRY) or 0.0 for _, _, a in rows)
        if total_baseline_cost > 0:
            pct = (1 - total_adaptive_cost / total_baseline_cost) * 100.0
            f.write(
                f"- Total projected cost across all 6 tasks: baseline ${total_baseline_cost:.6f}, "
                f"adaptive ${total_adaptive_cost:.6f} ({pct:.1f}% {'lower' if pct >= 0 else 'higher'} "
                "under adaptive) -- entirely a function of real published per-1K pricing differences "
                "between claude-opus-4-1 and the two adaptive-condition models, times real (mocked) "
                "token counts; MockProvider's output text/length does not depend on which model is "
                "configured, so this delta reflects routing choice and pricing only, not any "
                "difference in generation quality (mock providers do not vary by model).\n"
            )
        models_differed = sum(1 for _, b, a in rows if b.selected.split(":")[-1] != a.selected.split(":")[-1])
        f.write(
            f"- Adaptive selected a different model than the baseline on {models_differed}/{len(rows)} "
            "tasks (baseline is pinned to one model by construction, so this just reports how often "
            "adaptive's real complexity-based choice landed on the cheaper vs. the pricier of its two "
            "candidates).\n"
        )
        total_escalations = sum(a.escalation_count for _, _, a in rows)
        total_escalations += sum(b.escalation_count for _, b, _ in rows)
        f.write(
            f"- Total escalations observed across both conditions: {total_escalations}. This is "
            "not a gap in the test tasks -- it is structural: `MockProvider.generate()`'s "
            "truncation condition is `input_tokens > max_output_tokens`, and `Estimator."
            "estimate_task()` always sizes `output_budget_tokens` as at least `1.5x` the prompt's "
            "own token count, so `input_tokens > max_output_tokens` can never be true on a first "
            "attempt through this path, regardless of prompt length. Escalation logic "
            "(`suggest_escalation`) is real and unit-tested elsewhere (`tests/test_escalation.py`); "
            "this benchmark simply never exercises it end-to-end, and says so rather than "
            "fabricating a retry that didn't happen.\n"
        )
        f.write(
            "- Latency numbers above are Golden Boy's own code-path overhead under MockProvider "
            "(no network I/O at all); they are reported only because the task's measurement list "
            "calls for latency, and they are explicitly NOT a stand-in for real Anthropic/OpenAI "
            "API latency, which was not measured in this run.\n"
        )

    print(f"Results written to {md_path}")


if __name__ == "__main__":
    main()

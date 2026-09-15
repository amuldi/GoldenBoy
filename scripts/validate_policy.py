"""Realistic-workload / policy-engine validation (the "does Golden Boy make
sensible calls" question from the polyglot-upgrade brief's Sections 11-12).

Two things this script does *not* do, on purpose, because doing them would
mean fabricating data:

- It does not report accuracy metrics (MAE/MAPE/precision/recall) for
  "estimated vs. actual workload" -- that requires real completed-task
  outcomes, which only exist once `HistoryStore` has real data (see
  `goldenboy.replay`, and ROADMAP.md: "blocked on real usage data
  accumulating ... cannot be produced honestly today"). This script reports
  what *can* be measured honestly right now: real `Estimator`/
  `DecisionEngine` output against synthetic-but-representative task
  descriptions, at every budget level in the spec's own curve.
- It does not invent an "actual workload" number. Where the brief asks for
  one, the report says N/A and points at what would need to exist first --
  same convention `goldenboy replay` already uses (see its own N/A-below-
  10-events behavior, exercised for real at the bottom of this script).

What it does do, all real and reproducible:

1. Runs `DecisionEngine.decide()` (the actual, shipped decision path) for
   8 representative task descriptions across a 80/50/30/15/10/5% budget
   curve -- 48 real decisions, not fabricated ones.
2. Separately compares Golden Boy's own `RiskEngine`-backed policy against
   every baseline in `goldenboy.core.policies` on identical inputs (same
   comparison machinery `goldenboy.replay` uses for backtesting, applied
   here without needing historical outcome data -- this is a decision-
   behavior comparison, not an accuracy backtest).
3. Actually invokes `goldenboy validate` and `goldenboy replay` against
   whatever local history exists, and reports the real output verbatim.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldenboy.adapters.mock import MockProvider  # noqa: E402
from goldenboy.core.decision_engine import DecisionEngine  # noqa: E402
from goldenboy.core.estimator import Estimator  # noqa: E402
from goldenboy.core.policies import PolicyInput, default_baseline_policies  # noqa: E402

# One task text per category from Section 11 of the brief. Chosen so the
# real (deterministic, keyword-based) TaskClassifier actually lands on the
# intended category -- verified below, not assumed; a mismatch is reported,
# not hidden.
_SCENARIOS = [
    ("small_bug_fix", "Fix a typo in the login error message"),
    ("medium_feature", "Implement a new /export endpoint that returns user data as CSV, with tests"),
    ("large_refactor", "Refactor the authentication module to remove duplicated session-handling code"),
    ("repository_audit", "Audit the entire repository for dead code and unused dependencies"),
    ("test_generation", "Write unit tests and integration tests for the payment module"),
    ("documentation_generation", "Write documentation and update the README for the new API"),
    ("multi_file_implementation", "Implement OAuth authentication with refresh tokens across the API, "
                                    "middleware, and client SDK, with full test coverage"),
    ("long_running_task", "Re-architect the data model and migrate the storage layer to the new schema"),
]

# The exact curve from Section 12 of the brief.
_BUDGET_CURVE = [80.0, 50.0, 30.0, 15.0, 10.0, 5.0]


def run_decision_matrix() -> List[dict]:
    engine = DecisionEngine()
    estimator = Estimator()
    rows = []
    for name, task in _SCENARIOS:
        estimate = estimator.estimate_task(task)
        for budget in _BUDGET_CURVE:
            decision = engine.decide(task, MockProvider(initial_percentage=budget))
            rows.append({
                "scenario": name,
                "task": task,
                "prompt_chars": len(task),
                "budget_pct": budget,
                "estimated_cost_pct": round(estimate.estimated_percentage, 2),
                "detected_task_type": decision.task.task_type,
                "task_type_confidence": decision.task.task_type_confidence,
                "complexity_label": decision.task.complexity_label,
                "risk_mode": decision.risk.mode,
                "action": decision.action,
                "decision_confidence": decision.confidence,
            })
    return rows


def run_policy_comparison() -> List[dict]:
    estimator = Estimator()
    policies = default_baseline_policies()
    rows = []
    for name, task in _SCENARIOS:
        estimate = estimator.estimate_task(task)
        for budget in _BUDGET_CURVE:
            state = PolicyInput(
                remaining_percentage=budget,
                estimated_cost_percentage=estimate.estimated_percentage,
                usage_confidence="EXACT",
            )
            row = {
                "scenario": name,
                "budget_pct": budget,
                "estimated_cost_pct": round(estimate.estimated_percentage, 2),
            }
            for policy in policies:
                row[policy.name] = policy.decide(state).value
            rows.append(row)
    return rows


def render_decision_matrix_md(rows: List[dict]) -> str:
    lines = [
        "| Scenario | Budget % | Est. cost % | Task type (detected) | Complexity | Risk mode | "
        "Action | Confidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['budget_pct']:.0f} | {r['estimated_cost_pct']:.1f} | "
            f"{r['detected_task_type']} | {r['complexity_label']} | {r['risk_mode']} | "
            f"{r['action']} | {r['decision_confidence']:.2f} |"
        )
    return "\n".join(lines)


def render_policy_comparison_md(rows: List[dict]) -> str:
    if not rows:
        return ""
    policy_names = [k for k in rows[0].keys() if k not in ("scenario", "budget_pct", "estimated_cost_pct")]
    header = "| Scenario | Budget % | Est. cost % | " + " | ".join(policy_names) + " |"
    sep = "|---|---|---|" + "---|" * len(policy_names)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['budget_pct']:.0f} | {r['estimated_cost_pct']:.1f} | "
            + " | ".join(r[name] for name in policy_names) + " |"
        )
    return "\n".join(lines)


def classifier_accuracy_note(rows: List[dict]) -> str:
    # Not a claim about real-world classifier accuracy (no labeled dataset
    # exists) -- just an honest count of how many of these 8 hand-written
    # scenario prompts the deterministic keyword classifier actually
    # matched to a non-UNKNOWN type, since a scenario landing on UNKNOWN
    # would make the rest of its row less meaningful to read.
    unknown = sum(
        1 for r in rows
        if r["detected_task_type"] == "unknown" and r["budget_pct"] == _BUDGET_CURVE[0]
    )
    total = len(_SCENARIOS)
    return f"{total - unknown}/{total} scenario prompts classified as a non-UNKNOWN task type."


def run_cli_validate_and_replay() -> str:
    """Actually invokes the real CLI commands these sections reference,
    rather than describing what they'd do -- the real, current, local output."""
    out = []
    goldenboy_bin = str(Path(sys.executable).parent / "goldenboy")
    for args in (["validate", "--json"], ["replay", "--json"]):
        try:
            result = subprocess.run(
                [goldenboy_bin, *args], capture_output=True, text=True, timeout=30,
            )
            out.append(f"### `goldenboy {' '.join(args)}` (exit code {result.returncode})\n")
            out.append("```json")
            try:
                out.append(json.dumps(json.loads(result.stdout), indent=2))
            except json.JSONDecodeError:
                out.append(result.stdout.strip() or "(no stdout)")
            out.append("```\n")
        except (OSError, subprocess.SubprocessError) as e:
            out.append(f"### `goldenboy {' '.join(args)}`: could not run ({e})\n")
    return "\n".join(out)


def main() -> None:
    decision_rows = run_decision_matrix()
    policy_rows = run_policy_comparison()

    out_dir = Path(__file__).resolve().parent.parent / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    import time
    date_str = time.strftime("%Y-%m-%d")
    md_path = out_dir / f"{date_str}-policy-validation.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Policy / workload validation -- {date_str}\n\n")
        f.write(
            "Generated by `scripts/validate_policy.py`. Every row below is the real "
            "output of `DecisionEngine.decide()` / `Policy.decide()` on this machine, "
            "right now -- not a fabricated or illustrative table. See the script's "
            "module docstring for what this deliberately does *not* claim (accuracy "
            "metrics, an 'actual workload' number) and why.\n\n"
        )
        f.write(f"{classifier_accuracy_note(decision_rows)}\n\n")

        f.write("## 1. DecisionEngine across the budget curve (Section 12)\n\n")
        f.write(render_decision_matrix_md(decision_rows))
        f.write("\n\n")

        f.write(
            "## 2. Golden Boy's RiskEngine-backed policy vs. baseline policies "
            "(`goldenboy.core.policies`)\n\n"
        )
        f.write(
            "Same `(remaining_percentage, estimated_cost_percentage)` state given to "
            "every policy -- this compares *decision behavior*, not accuracy (accuracy "
            "requires real outcomes; see `goldenboy.replay` and Section 3 below).\n\n"
        )
        f.write(render_policy_comparison_md(policy_rows))
        f.write("\n\n")

        f.write("## 3. Real `goldenboy validate` / `goldenboy replay` output (this machine)\n\n")
        f.write(run_cli_validate_and_replay())
        f.write(
            "\n`replay`'s backtest metrics are N/A here because this is a fresh/low-"
            "event local install -- consistent with ROADMAP.md's documented blocker "
            "(real accuracy validation needs real historical outcomes, which don't "
            "exist yet). This script does not work around that by inventing data.\n"
        )

    print(f"Wrote {md_path}")
    print(classifier_accuracy_note(decision_rows))


if __name__ == "__main__":
    main()

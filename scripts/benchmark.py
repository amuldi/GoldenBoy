#!/usr/bin/env python3
"""Minimal, honest benchmark harness for Golden Boy.

Measures things that are actually measurable without a live provider API
(no network calls, no fabricated numbers): estimator latency, risk
assessment latency, and CLI cold-start time. Run it yourself and read the
numbers it prints -- don't trust numbers pasted into a README, including
this project's own (see BENCHMARKS.md for the most recent run and its
caveats: single machine, single run, no statistical rigor implied).

Usage:
    python scripts/benchmark.py
"""
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldenboy.core.budget import Budget
from goldenboy.core.estimator import Estimator
from goldenboy.core.risk import RiskEngine


def _time_it(fn, iterations: int):
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def _report(label: str, samples, unit="ms"):
    scale = 1000 if unit == "ms" else 1
    scaled = [s * scale for s in samples]
    print(
        f"{label}: "
        f"mean={statistics.mean(scaled):.3f}{unit} "
        f"median={statistics.median(scaled):.3f}{unit} "
        f"min={min(scaled):.3f}{unit} "
        f"max={max(scaled):.3f}{unit} "
        f"(n={len(scaled)})"
    )


def benchmark_estimator():
    estimator = Estimator()
    task = "Implement OAuth authentication with refresh tokens and tests"
    samples = _time_it(lambda: estimator.estimate_task(task), iterations=20)
    _report("Estimator.estimate_task() [warm, this repo]", samples)

    # Determinism check: identical input -> identical output, every time.
    # This is a real invariant, not a speed number -- report pass/fail.
    results = {estimator.estimate_task(task).estimated_percentage for _ in range(10)}
    print(f"Estimator.estimate_task() determinism: {'PASS' if len(results) == 1 else 'FAIL'} "
          f"({len(results)} distinct result(s) across 10 identical calls)")


def benchmark_risk_engine():
    engine = RiskEngine()
    budget = Budget(remaining_percentage=40.0)
    from goldenboy.core.estimator import TaskEstimate
    estimate = TaskEstimate(estimated_percentage=15.0, confidence=0.9)
    samples = _time_it(lambda: engine.assess(budget, estimate), iterations=1000)
    _report("RiskEngine.assess()", samples, unit="ms")


def benchmark_cli_startup():
    # Cold subprocess start -- this is what a user actually experiences
    # running `goldenboy status`, including Python/import overhead.
    goldenboy_bin = str(Path(sys.executable).parent / "goldenboy")
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        subprocess.run(
            [goldenboy_bin, "status", "--budget", "50"],
            capture_output=True, check=True,
        )
        samples.append(time.perf_counter() - start)
    _report("CLI cold start (`goldenboy status`)", samples)


if __name__ == "__main__":
    print(f"Golden Boy benchmark — {sys.version.split()[0]} on {sys.platform}\n")
    print(
        "Methodology: wall-clock time via time.perf_counter(), single process, "
        "no warmup beyond what's noted, this machine only. Not a substitute for "
        "profiling under real load; treat as a rough, reproducible signal, not "
        "a performance guarantee.\n"
    )
    benchmark_estimator()
    benchmark_risk_engine()
    benchmark_cli_startup()

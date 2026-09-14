"""Shared implementation behind both `scripts/benchmark.py` and
`goldenboy benchmark` -- one measurement path, not two copies of it.

Measures things that are actually measurable locally (no network calls, no
fabricated numbers): estimator latency, risk-assessment latency, and CLI
cold-start time. See BENCHMARKS.md for the most recent recorded run and its
caveats (single machine, single run, no statistical rigor implied) -- this
module does not read or write that file; it only produces numbers, on
whatever machine it's run on, right now.
"""
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class LatencySample:
    label: str
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    n: int

    def render(self) -> str:
        return (
            f"{self.label}: mean={self.mean_ms:.3f}ms median={self.median_ms:.3f}ms "
            f"min={self.min_ms:.3f}ms max={self.max_ms:.3f}ms (n={self.n})"
        )


@dataclass
class BenchmarkReport:
    platform: str
    python_version: str
    estimator_latency: Optional[LatencySample]
    estimator_determinism_pass: Optional[bool]
    estimator_distinct_results: Optional[int]
    risk_engine_latency: Optional[LatencySample]
    cli_startup_latency: Optional[LatencySample]
    errors: Dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f"Golden Boy benchmark — {self.python_version} on {self.platform}", ""]
        if self.estimator_latency:
            lines.append(self.estimator_latency.render())
        if self.estimator_determinism_pass is not None:
            lines.append(
                f"Estimator.estimate_task() determinism: "
                f"{'PASS' if self.estimator_determinism_pass else 'FAIL'} "
                f"({self.estimator_distinct_results} distinct result(s) across 10 identical calls)"
            )
        if self.risk_engine_latency:
            lines.append(self.risk_engine_latency.render())
        if self.cli_startup_latency:
            lines.append(self.cli_startup_latency.render())
        for label, error in self.errors.items():
            lines.append(f"{label}: SKIPPED ({error})")
        return "\n".join(lines)


def _time_it(fn, iterations: int) -> List[float]:
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def _sample(label: str, raw_samples: List[float]) -> LatencySample:
    scaled = [s * 1000 for s in raw_samples]
    return LatencySample(
        label=label,
        mean_ms=statistics.mean(scaled),
        median_ms=statistics.median(scaled),
        min_ms=min(scaled),
        max_ms=max(scaled),
        n=len(scaled),
    )


def benchmark_estimator():
    from goldenboy.core.estimator import Estimator

    estimator = Estimator()
    task = "Implement OAuth authentication with refresh tokens and tests"
    samples = _time_it(lambda: estimator.estimate_task(task), iterations=20)
    latency = _sample("Estimator.estimate_task() [warm, this repo]", samples)

    results = {estimator.estimate_task(task).estimated_percentage for _ in range(10)}
    return latency, len(results) == 1, len(results)


def benchmark_risk_engine():
    from goldenboy.core.budget import Budget
    from goldenboy.core.estimator import TaskEstimate
    from goldenboy.core.risk import RiskEngine

    engine = RiskEngine()
    budget = Budget(remaining_percentage=40.0)
    estimate = TaskEstimate(estimated_percentage=15.0, confidence=0.9)
    samples = _time_it(lambda: engine.assess(budget, estimate), iterations=1000)
    return _sample("RiskEngine.assess()", samples)


def benchmark_cli_startup():
    goldenboy_bin = str(Path(sys.executable).parent / "goldenboy")
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        subprocess.run(
            [goldenboy_bin, "status", "--budget", "50"],
            capture_output=True, check=True,
        )
        samples.append(time.perf_counter() - start)
    return _sample("CLI cold start (`goldenboy status`)", samples)


def run_all() -> BenchmarkReport:
    """Runs every benchmark, catching and recording (never silently
    swallowing) any individual failure -- e.g. `benchmark_cli_startup` needs
    an installed console-script entry point, which isn't guaranteed to
    exist when running from an editable/source checkout without it."""
    errors: Dict[str, str] = {}

    estimator_latency = estimator_determinism = estimator_distinct = None
    try:
        estimator_latency, estimator_determinism, estimator_distinct = benchmark_estimator()
    except Exception as e:  # pragma: no cover - defensive
        errors["estimator"] = str(e)

    risk_latency = None
    try:
        risk_latency = benchmark_risk_engine()
    except Exception as e:  # pragma: no cover - defensive
        errors["risk_engine"] = str(e)

    cli_latency = None
    try:
        cli_latency = benchmark_cli_startup()
    except Exception as e:
        errors["cli_startup"] = str(e)

    return BenchmarkReport(
        platform=sys.platform,
        python_version=sys.version.split()[0],
        estimator_latency=estimator_latency,
        estimator_determinism_pass=estimator_determinism,
        estimator_distinct_results=estimator_distinct,
        risk_engine_latency=risk_latency,
        cli_startup_latency=cli_latency,
        errors=errors,
    )

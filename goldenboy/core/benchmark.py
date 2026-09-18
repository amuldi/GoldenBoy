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
    policy_engine_latency: Optional[LatencySample] = None
    model_router_latency: Optional[LatencySample] = None
    audit_log_write_latency: Optional[LatencySample] = None
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
        if self.policy_engine_latency:
            lines.append(self.policy_engine_latency.render())
        if self.model_router_latency:
            lines.append(self.model_router_latency.render())
        if self.audit_log_write_latency:
            lines.append(self.audit_log_write_latency.render())
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


def benchmark_policy_engine():
    from goldenboy.core.governance import ActionRequest, PolicyConfig, PolicyEngine

    engine = PolicyEngine(config=PolicyConfig())
    request = ActionRequest(
        tool="bash", command="pytest tests/ && ruff check .", estimated_cost_percentage=5.0
    )
    samples = _time_it(lambda: engine.evaluate(request), iterations=200)
    return _sample("PolicyEngine.evaluate()", samples)


def benchmark_model_router():
    from goldenboy.core.risk import ExecutionMode
    from goldenboy.core.router import ModelRouter, RouterConfig

    router = ModelRouter(config=RouterConfig())
    samples = _time_it(lambda: router.route("HIGH", ExecutionMode.CAUTION), iterations=200)
    return _sample("ModelRouter.route()", samples)


def benchmark_audit_log_write():
    import shutil
    import tempfile

    from goldenboy.core.audit import AuditEntry, AuditStore

    tmp_dir = tempfile.mkdtemp(prefix="goldenboy-benchmark-audit-")
    try:
        store = AuditStore(history_dir=tmp_dir)
        entry = AuditEntry.create(
            action="policy_check", result="success", tool="bash", decision="allow",
            policy_result="ALLOWED", estimated_cost=5.0,
        )
        samples = _time_it(lambda: store.record(entry), iterations=200)
        return _sample("AuditStore.record() [local disk write]", samples)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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

    policy_latency = None
    try:
        policy_latency = benchmark_policy_engine()
    except Exception as e:  # pragma: no cover - defensive
        errors["policy_engine"] = str(e)

    router_latency = None
    try:
        router_latency = benchmark_model_router()
    except Exception as e:  # pragma: no cover - defensive
        errors["model_router"] = str(e)

    audit_latency = None
    try:
        audit_latency = benchmark_audit_log_write()
    except Exception as e:  # pragma: no cover - defensive
        errors["audit_log_write"] = str(e)

    return BenchmarkReport(
        platform=sys.platform,
        python_version=sys.version.split()[0],
        estimator_latency=estimator_latency,
        estimator_determinism_pass=estimator_determinism,
        estimator_distinct_results=estimator_distinct,
        risk_engine_latency=risk_latency,
        cli_startup_latency=cli_latency,
        policy_engine_latency=policy_latency,
        model_router_latency=router_latency,
        audit_log_write_latency=audit_latency,
        errors=errors,
    )

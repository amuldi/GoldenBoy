#!/usr/bin/env python3
"""Minimal, honest benchmark harness for Golden Boy.

Thin wrapper around `goldenboy.core.benchmark` (also used by the
`goldenboy benchmark` CLI command, so there is exactly one measurement
implementation, not two copies of it). Measures things that are actually
measurable without a live provider API (no network calls, no fabricated
numbers): estimator latency, risk assessment latency, and CLI cold-start
time. Run it yourself and read the numbers it prints -- don't trust
numbers pasted into a README, including this project's own (see
BENCHMARKS.md for the most recent run and its caveats: single machine,
single run, no statistical rigor implied).

Usage:
    python scripts/benchmark.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldenboy.core.benchmark import run_all  # noqa: E402

if __name__ == "__main__":
    report = run_all()
    print(report.render())
    print(
        "\nMethodology: wall-clock time via time.perf_counter(), single process, "
        "no warmup beyond what's noted, this machine only. Not a substitute for "
        "profiling under real load; treat as a rough, reproducible signal, not "
        "a performance guarantee."
    )

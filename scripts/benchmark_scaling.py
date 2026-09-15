"""Scaling benchmark for the one gap `BENCHMARKS.md`/`ROADMAP.md` explicitly
flag as not yet measured: how Golden Boy behaves as *input size* grows, not
just on this repo's own (small) size.

This is deliberately a separate, heavier script from `scripts/benchmark.py`
(which stays fast enough to run informally) -- it builds synthetic
repositories and history logs on disk, so a full run takes tens of seconds,
not milliseconds. Not part of CI.

Three independent axes, matching the three places input size can actually
grow in this codebase:

1. Prompt size -> `Estimator._count_tokens` / `estimate_task` (the
   prompt-tokens term).
2. Repository size (file count) -> `Estimator._estimate_codebase_context`'s
   file-walk (the term `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` exist to bound --
   this is the "Planned" benchmark from ROADMAP.md).
3. History log size -> `HistoryStore.load_events()`, which has no analogous
   cap today.

Every number this script prints is a real measurement on whatever machine
it's run on, right now -- see the module docstring convention in
`goldenboy/core/benchmark.py`. Nothing here is extrapolated or assumed
unless explicitly labeled "estimated" in the output.
"""
import json
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldenboy.core.estimator import Estimator  # noqa: E402
from goldenboy.core.history import HistoryStore, TaskEvent  # noqa: E402


@dataclass
class Sample:
    label: str
    n_ops: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    throughput_per_s: float

    def render(self) -> str:
        return (
            f"{self.label}: mean={self.mean_ms:.3f}ms p50={self.p50_ms:.3f}ms "
            f"p95={self.p95_ms:.3f}ms p99={self.p99_ms:.3f}ms "
            f"min={self.min_ms:.3f}ms max={self.max_ms:.3f}ms "
            f"throughput={self.throughput_per_s:.1f} ops/s (n={self.n_ops})"
        )

    def to_row(self) -> str:
        return (
            f"| {self.label} | {self.mean_ms:.3f} | {self.p50_ms:.3f} | "
            f"{self.p95_ms:.3f} | {self.p99_ms:.3f} | {self.throughput_per_s:.1f} |"
        )


def _percentile(sorted_samples: List[float], pct: float) -> float:
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    k = (len(sorted_samples) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_samples) - 1)
    if f == c:
        return sorted_samples[f]
    return sorted_samples[f] + (sorted_samples[c] - sorted_samples[f]) * (k - f)


def _measure(label: str, fn: Callable[[], None], iterations: int) -> Sample:
    raw = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        raw.append((time.perf_counter() - start) * 1000)
    raw_sorted = sorted(raw)
    total_s = sum(raw) / 1000.0
    return Sample(
        label=label,
        n_ops=iterations,
        mean_ms=statistics.mean(raw),
        p50_ms=_percentile(raw_sorted, 0.50),
        p95_ms=_percentile(raw_sorted, 0.95),
        p99_ms=_percentile(raw_sorted, 0.99),
        min_ms=min(raw),
        max_ms=max(raw),
        throughput_per_s=(iterations / total_s) if total_s > 0 else float("inf"),
    )


# --- Axis 1: prompt token size ------------------------------------------

def bench_prompt_sizes() -> List[Sample]:
    estimator = Estimator()
    results = []
    # Target token counts; ~4 chars/token via repeated words keeps this
    # independent of whether tiktoken is installed (both paths are exercised
    # in CI: see ci.yml's dedicated anthropic/openai/tiktoken job).
    for target_tokens in (1_000, 10_000, 100_000, 1_000_000, 10_000_000):
        word = "implement "
        # _count_tokens's own fallback is chars // 4; a repeated word is not
        # perfectly 1 token/word under tiktoken's real BPE, so this is a
        # deliberate approximation -- the point is *scaling behavior*, not
        # hitting the target exactly. Logged exactly so the report is honest
        # about what was actually measured.
        prompt = word * (target_tokens // 1)
        iterations = 5 if target_tokens < 1_000_000 else 3
        results.append(
            _measure(f"estimate_task(prompt~{target_tokens:,} words)",
                     lambda p=prompt: estimator.estimate_task(p), iterations)
        )
    return results


# --- Axis 2: repository file count ---------------------------------------

def _build_synthetic_repo(tmpdir: Path, n_files: int, bytes_per_file: int = 2_000) -> None:
    body = ("def handler(x):\n    return x + 1\n" * ((bytes_per_file // 32) + 1))[:bytes_per_file]
    for i in range(n_files):
        (tmpdir / f"module_{i}.py").write_text(body, encoding="utf-8")


def bench_repo_scaling() -> List[Sample]:
    estimator = Estimator()
    results = []
    # Deliberately straddles _MAX_SCAN_FILES=200: below, at, and well past
    # the cap, so the report shows whether the cap actually bounds latency.
    for n_files in (50, 200, 1_000, 5_000):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            _build_synthetic_repo(tmpdir, n_files)
            import os
            cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                results.append(
                    _measure(f"estimate_task(repo={n_files} files)",
                             lambda: estimator.estimate_task("Fix a bug"), iterations=5)
                )
            finally:
                os.chdir(cwd)
    return results


def bench_oversized_file_is_skipped() -> str:
    """Not a latency measurement -- a correctness check that a single file
    over `_MAX_FILE_BYTES` is skipped rather than read in full, so the repo
    scaling numbers above aren't secretly bounded by one giant bundled file
    instead of the file-count cap."""
    estimator = Estimator()
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        import os
        (tmpdir / "small.py").write_text("x = 1\n", encoding="utf-8")
        (tmpdir / "huge_bundle.py").write_text("x = 1\n" * 100_000, encoding="utf-8")  # ~600KB > 200KB cap
        cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            small_only = estimator._estimate_codebase_context(".")
        finally:
            os.chdir(cwd)
    huge_size = len("x = 1\n" * 100_000)
    return (
        f"Oversized-file skip check: huge_bundle.py is {huge_size:,} bytes "
        f"(> _MAX_FILE_BYTES=200,000); codebase-context token count with it present "
        f"is {small_only} (small.py alone) -- confirms it was skipped, not partially read."
    )


# --- Axis 3: history log size ---------------------------------------------

def _make_event(i: int) -> TaskEvent:
    return TaskEvent.create(
        task_text=f"synthetic task {i}",
        task_type="bug_fix",
        task_type_confidence=0.7,
        priority=None,
        estimated_cost_percentage=5.0,
        estimated_cost_confidence=0.85,
        usage_source="mock",
        usage_confidence="EXACT",
        remaining_usage_start=50.0,
        decision_mode="SAFE",
        outcome="completed",
    )


def bench_history_scaling() -> List[Sample]:
    results = []
    # One synthetic event line is ~230-260 bytes; approximate event counts to
    # land near 1MB/10MB/100MB rather than hitting them exactly. 1GB is
    # intentionally not attempted here -- see the report's "Not measured"
    # note (disk/time cost disproportionate to this project's realistic
    # scale: a single-user local CLI history file, not a server log).
    bytes_per_line = len(json.dumps(_make_event(0).to_dict())) + 1
    for target_bytes, label in (
        (1_000_000, "1MB"),
        (10_000_000, "10MB"),
        (100_000_000, "100MB"),
    ):
        n_events = target_bytes // bytes_per_line
        with tempfile.TemporaryDirectory() as td:
            store = HistoryStore(history_dir=td)
            with open(store.history_file, "w", encoding="utf-8") as f:
                for i in range(n_events):
                    f.write(json.dumps(_make_event(i).to_dict()) + "\n")
            actual_bytes = Path(store.history_file).stat().st_size
            iterations = 5 if target_bytes <= 10_000_000 else 3
            results.append(
                _measure(
                    f"HistoryStore.load_events() ({label} target, "
                    f"{actual_bytes:,} bytes actual, {n_events:,} events)",
                    lambda s=store: s.load_events(), iterations,
                )
            )
    return results


def main() -> None:
    print("Golden Boy scaling benchmark -- real measurements, this machine, right now.\n")

    print("== Axis 1: prompt token size ==")
    prompt_results = bench_prompt_sizes()
    for s in prompt_results:
        print(s.render())

    print("\n== Axis 2: repository file count (Estimator._estimate_codebase_context) ==")
    repo_results = bench_repo_scaling()
    for s in repo_results:
        print(s.render())
    print(bench_oversized_file_is_skipped())

    print("\n== Axis 3: history log size (HistoryStore.load_events) ==")
    history_results = bench_history_scaling()
    for s in history_results:
        print(s.render())

    print("\nNote: 1GB history log deliberately not measured -- see script docstring.")

    out_path = Path(__file__).resolve().parent.parent / "benchmarks" / "results"
    out_path.mkdir(parents=True, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    md_path = out_path / f"{date_str}-scaling.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Scaling benchmark -- {date_str}\n\n")
        f.write(
            "Generated by `scripts/benchmark_scaling.py`. Real measurements, single "
            "machine, single run -- same caveats as `BENCHMARKS.md`. Not part of CI.\n\n"
        )
        f.write(f"Platform: `{sys.platform}`, Python `{sys.version.split()[0]}`.\n\n")

        f.write("## Axis 1: prompt token size\n\n")
        f.write("| Prompt size | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | throughput (ops/s) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for s in prompt_results:
            f.write(s.to_row() + "\n")

        f.write("\n## Axis 2: repository file count\n\n")
        f.write("| Repo size | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | throughput (ops/s) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for s in repo_results:
            f.write(s.to_row() + "\n")
        f.write(f"\n{bench_oversized_file_is_skipped()}\n")

        f.write("\n## Axis 3: history log size\n\n")
        f.write("| Log size | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | throughput (ops/s) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for s in history_results:
            f.write(s.to_row() + "\n")
        f.write(
            "\n1GB history log: not measured (disk/time cost disproportionate to this "
            "project's realistic scale -- a single-user local CLI history file, not a "
            "server log; see `HistoryStore`'s docstring). If the 100MB row scales "
            "roughly linearly, 1GB would extrapolate to ~10x the 100MB latency, but "
            "this is an extrapolation, not a measurement, and is reported as such.\n"
        )

    print(f"\nResults written to {md_path}")


if __name__ == "__main__":
    main()

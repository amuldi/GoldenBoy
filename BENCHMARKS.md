# Benchmarks

Golden Boy does not publish performance claims it hasn't measured. This
file records the output of `scripts/benchmark.py`, run manually, with the
exact machine and date attached. It is not part of CI and not a guarantee
— re-run it yourself (`python scripts/benchmark.py`) before relying on
these numbers for anything.

## What's measured (and what isn't)

Measured: estimator latency and determinism, risk-assessment latency, CLI
cold-start time — all local, no network calls.

Not yet measured (Research in `ROADMAP.md`): anything involving a real
provider API call (`refresh_usage()` latency depends entirely on network/API
conditions outside Golden Boy's control, so a number here would mostly
measure the network, not Golden Boy), memory usage under sustained use,
and behavior at large repository scale (this repo is small; the
`_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` caps in `estimator.py` exist
specifically to bound worst-case behavior, but the bound itself hasn't
been benchmarked against a deliberately large synthetic repo).

## 2026-09-13 — Apple M1 Pro, macOS (arm64), Python 3.13.7

```
Estimator.estimate_task() [warm, this repo]: mean=9.298ms median=8.787ms min=8.355ms max=18.782ms (n=20)
Estimator.estimate_task() determinism: PASS (1 distinct result(s) across 10 identical calls)
RiskEngine.assess(): mean=0.000ms median=0.000ms min=0.000ms max=0.005ms (n=1000)
CLI cold start (`goldenboy status`): mean=93.457ms median=93.334ms min=91.306ms max=96.018ms (n=5)
```

Reading these honestly:

- **RiskEngine.assess()** is pure arithmetic on already-computed values — sub-microsecond, as expected, and not really a meaningful thing to optimize further.
- **Estimator.estimate_task()** (~9ms here) is dominated by walking this repository's own source tree; it scales with repository size up to the `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES` caps, not with prompt length.
- **CLI cold start** (~93ms) is mostly Python interpreter + import overhead, not Golden Boy-specific logic — this is what a user actually feels running any single `goldenboy` command.

These were run once, on one machine, with no other load. Treat them as a rough order-of-magnitude signal, not a benchmark suite result.

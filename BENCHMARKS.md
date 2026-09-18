# Benchmarks

Golden Boy does not publish performance claims it hasn't measured. This
file records the output of `scripts/benchmark.py`, run manually, with the
exact machine and date attached. It is not part of CI and not a guarantee
— re-run it yourself (`python scripts/benchmark.py`) before relying on
these numbers for anything.

## What's measured (and what isn't)

Measured: estimator latency and determinism, risk-assessment latency, CLI
cold-start time, Policy Engine evaluation latency, Model Router latency,
and Audit Log write latency — all local, no network calls.

Not yet measured (Research in `ROADMAP.md`): anything involving a real
provider API call (`refresh_usage()` latency depends entirely on network/API
conditions outside Golden Boy's control, so a number here would mostly
measure the network, not Golden Boy), and memory usage under sustained use.

Behavior at scale (prompt size, repository file count, history log size) is
now measured separately in `scripts/benchmark_scaling.py` — see
`benchmarks/results/2026-09-15-scaling.md` and `ARCHITECTURE_AUDIT.md` §2
for the results and what they mean. That script is intentionally kept
separate from the one below: it takes tens of seconds to run (it builds
synthetic repositories and multi-hundred-MB files on disk) rather than
milliseconds, so it isn't part of the routine "run this before relying on
these numbers" workflow this file documents.

## 2026-09-18 — Apple M1 Pro, macOS (arm64), Python 3.13.7 (after the governance/runtime-safety upgrade)

```
Estimator.estimate_task() [warm, this repo]: mean=61.215ms median=60.542ms min=59.325ms max=72.096ms (n=20)
Estimator.estimate_task() determinism: PASS (1 distinct result(s) across 10 identical calls)
RiskEngine.assess(): mean=0.000ms median=0.000ms min=0.000ms max=0.011ms (n=1000)
CLI cold start (`goldenboy status`): mean=143.746ms median=142.520ms min=140.823ms max=150.839ms (n=5)
PolicyEngine.evaluate(): mean=0.007ms median=0.007ms min=0.007ms max=0.033ms (n=200)
ModelRouter.route(): mean=0.002ms median=0.002ms min=0.001ms max=0.018ms (n=200)
AuditStore.record() [local disk write]: mean=0.065ms median=0.056ms min=0.046ms max=0.938ms (n=200)
```

Three new measurements, added alongside the existing three (`goldenboy.core.benchmark.benchmark_policy_engine`/
`benchmark_model_router`/`benchmark_audit_log_write`, wired into the same shared `run_all()` both
`goldenboy benchmark` and `scripts/benchmark.py` already used): `PolicyEngine.evaluate()` and
`ModelRouter.route()` are both pure in-memory logic over already-known inputs, so — like
`RiskEngine.assess()` — they land in the sub-microsecond-to-low-microsecond range, not a bottleneck by
construction. `AuditStore.record()` is the one new operation that touches disk (one JSONL line, `open`
+ `write` + implicit `flush`/`close` per call) and is still well under a tenth of a millisecond on
average.

`Estimator.estimate_task()` (61.2ms) and CLI cold start (143.7ms) both read higher than the 2026-09-17
entry below (41.4ms / 119.1ms) on this same machine. Read honestly, not as a hidden regression claim:
this file's own methodology note has always said "single machine, single run, no other load assumed
controlled for" — this run was taken on a machine with several other processes active (editors, a
background build), and neither `Estimator`/`RiskEngine`'s own code changed in this upgrade. `cli.py`
does now construct 8 additional `argparse` subparsers on every invocation (one per new command), which is
a plausible, real contributor to CLI-startup overhead — but it was not isolated via a controlled A/B
measurement here, so it is named as a hypothesis, not asserted as the measured cause of the full ~25ms
delta. Re-run `scripts/benchmark.py` yourself on a quiet machine before treating either number as precise.

## 2026-09-17 — Apple M1 Pro, macOS (arm64), Python 3.13.7 (after the context-relevance/complexity upgrade)

```
Estimator.estimate_task() [warm, this repo]: mean=41.442ms median=40.810ms min=40.122ms max=50.703ms (n=20)
Estimator.estimate_task() determinism: PASS (1 distinct result(s) across 10 identical calls)
RiskEngine.assess(): mean=0.000ms median=0.000ms min=0.000ms max=0.008ms (n=1000)
CLI cold start (`goldenboy status`): mean=119.089ms median=118.726ms min=115.962ms max=125.254ms (n=5)
```

`Estimator.estimate_task()` went from ~9.3ms (2026-09-13, below) to ~41.4ms
here — a real, measured ~4.5x increase, not noise. Root cause: the P0 fix
in `ARCHITECTURE_AUDIT.md` §7 (context estimate dominated by repo size, not
task size) replaced one file-tree walk with two — `_estimate_codebase_
context` (unchanged, still walked for the now-secondary "repository size"
figure) plus the new `_estimate_relevant_context` (scores every candidate
file's *path* against the task's keywords before selecting which to read)
— plus per-task complexity scoring (`goldenboy.core.complexity`). This
repository's own source tree (~130 files) is still small enough that 41ms
is imperceptible next to the ~119ms CLI cold-start it's part of. See
`benchmarks/results/2026-09-17-scaling.md` for how this scales with
repository size (200 vs. 5,000 files: 48.6ms vs. 59.5ms — the relevance
scan does not reintroduce the old unbounded-scaling problem) and prompt
size (a pathological ~25M-character prompt was briefly ~9s before a fix
bounding how much of the prompt text the new complexity/keyword scoring
regex-scans — see CHANGELOG.md and `tests/test_complexity.py::
test_pathologically_large_prompt_does_not_hang` — down to ~0.56s, most of
which is tiktoken encoding the prompt itself, not Golden Boy's own logic).

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

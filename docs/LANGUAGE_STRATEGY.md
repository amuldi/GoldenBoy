# Language Strategy

## Why Python remains the core

Golden Boy's core (`goldenboy/`) stays in Python for v1.x. This was
reconsidered, not assumed, while building the protocol/SDK boundary
(2026-09-14) — see the measurements below before treating this as settled.

Reasons it's the right choice right now, not just the incumbent:

- **Nothing is actually slow.** See [Benchmarks](#benchmarks-behind-this-decision)
  — every measured operation is sub-20ms, most sub-millisecond. A rewrite
  buys speed nothing is waiting on.
- **The two real integration points are Python-native.** `AnthropicAdapter`/
  `OpenAIAdapter` wrap `anthropic`/`openai`'s official Python SDKs; the
  `skills/goldenboy/SKILL.md` prompt-level integration needs no runtime at
  all. Neither benefits from a Rust core underneath them.
- **Zero required dependencies is already the differentiator**, not
  raw speed — `pip install goldenboy` pulling nothing is what "lightweight"
  means for this project (see the README's Design Principles). A Rust
  core would trade that for a compiled-extension build/distribution
  story (per-platform wheels, a toolchain requirement for contributors)
  without a measured problem it solves.
- **The actual language-boundary need was a stable protocol, not a
  faster runtime** — which is what `goldenboy/protocol.py` +
  `sdk/typescript` deliver today, at a fraction of the cost of a Rust
  rewrite.

## Benchmarks behind this decision

From `goldenboy benchmark` / `scripts/benchmark.py` (see `BENCHMARKS.md`
for the full, dated methodology and caveats — single machine, single run,
not a guarantee):

| Operation | Latency |
|---|---|
| `RiskEngine.assess()` | sub-microsecond (pure arithmetic on already-computed values) |
| `Estimator.estimate_task()` | ~9-20ms, warm, this repo (dominated by walking the repo's own source tree, not Python overhead) |
| CLI cold start (`goldenboy status`) | ~90-110ms (mostly Python interpreter/import overhead) |

The only one of these with headroom to matter is CLI cold start, and even
that is dominated by interpreter startup, not by anything `goldenboy/core/`
computes — a concern about `python -m goldenboy` invocation overhead, not
about the decision logic itself being slow.

## Where TypeScript is used

`sdk/typescript/` is a **thin client**, not a second implementation.
`GoldenBoyClient` spawns the real `goldenboy` CLI and parses its `--json`
output through the same protocol validation the Python side enforces
(`goldenboy/protocol.py` ↔ `sdk/typescript/src/validate.ts`, kept in sync
by hand). No cost estimation, task classification, or risk logic exists
twice — see `sdk/typescript/README.md`'s "Design notes."

## Future Rust migration boundary

Not planned for v1.x; if a real bottleneck emerges (see
`ROADMAP.md`: "Benchmarking behavior against a deliberately large synthetic
repository" is Planned, not done — this is the one place a bottleneck
could plausibly show up as repos scale far beyond this project's own
size), the natural candidates, in order of how cleanly they're already
isolated behind a Python-facing interface:

1. **`Estimator._estimate_codebase_context`'s file-walking/token-counting
   loop** — already the slowest measured operation, already bounded by
   `_MAX_SCAN_FILES`/`_MAX_FILE_BYTES`, and already behind a single method
   call with no other module depending on its internals. The cleanest
   possible extraction point if repo-scanning ever needs to be much
   faster than the current bound allows.
2. **High-frequency local event processing** — if `HistoryStore`/
   `goldenboy.analytics` ever needs to process a history log far larger
   than a local CLI tool's realistic scale (thousands of events, not
   millions), the JSONL parse/aggregate loop is the next candidate.
3. **`RiskEngine`/`DecisionEngine`'s core arithmetic** — last on this
   list on purpose: it's already sub-microsecond in Python. Moving it to
   Rust would add a build/distribution burden (compiled extension wheels
   per platform) for a component that isn't measurably slow by any
   realistic standard.

Any of these would be introduced as an **optional accelerated path**
behind the same Python interface (mirroring how `tiktoken` is an optional
extra today, not a required one) — never a rewrite that drops the
zero-required-dependency, `pip install goldenboy`-and-go install story
this project is built around, and never before a benchmark demonstrates
the current pure-Python path is actually the bottleneck for a real use
case.

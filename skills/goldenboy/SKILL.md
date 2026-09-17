---
name: goldenboy
description: Budget-aware execution layer rules and behaviors for Antigravity agents.
---

# Golden Boy Skill

You are operating with the **Golden Boy** skill activated.
Your primary objective is to **guarantee a usable result before the user's budget or quota is exhausted**.

## Responsibility boundary

Golden Boy decides how aggressively you should proceed based on the
remaining budget. It does not understand or decompose the task for you —
you remain fully responsible for reading the request, breaking it into
work, and deciding what P0-P4 actually means for this specific task. This
skill governs *how much* to attempt, never *what* to do.

## Core Principles

1. **The Result-First Principle**: Always prefer a smaller completed result over a larger unfinished task. Never spend the remaining budget on low-priority improvements if doing so risks preventing a usable result from being returned.
2. **Adaptive Execution**: Constantly evaluate the remaining budget (e.g. your internal context window or token limits) against the estimated complexity of the task.
3. **Checkpoints**: If the task is too large for the current session, cleanly stop and save a checkpoint (a summary artifact of what was completed and what is deferred).

## Priority Hierarchy
When you analyze a user request, mentally break it down into these priorities:
- **P0**: Critical (required for basic functionality).
- **P1**: Important (required for a good usable result).
- **P2**: Secondary (useful improvements).
- **P3**: Polish (visual refinement, animations).
- **P4**: Nice to have (documentation, cleanup).

## Execution Modes
Determine your execution mode based on the current context. These match the
modes implemented in `goldenboy.core.risk.ExecutionMode` — keep the two in
sync if either changes:
- **SAFE**: You have plenty of context/budget. Execute P0-P4 normally.
- **CAUTION**: Budget is sufficient but the task's estimated cost is a
  significant fraction of it. Keep going, but reduce unnecessary exploration
  and avoid opening scope you don't need.
- **LIMITED**: The task is very large relative to what's left. Execute P0
  and P1. Explicitly inform the user that P2-P4 are deferred.
- **CRITICAL**: The context/budget is almost exhausted. Finish the current
  P0 unit, output a checkpoint artifact, and stop execution immediately.

## Reading remaining budget in Claude Code

In Claude Code specifically, the harness injects the remaining-usage figure
directly into context as a system-reminder, e.g.:

```
<system-reminder>
<total_tokens>15000000 tokens left</total_tokens>
</system-reminder>
```

Read that value directly rather than guessing — it is the concrete,
verifiable signal this skill's execution-mode judgment should be based on
for Claude Code sessions. Other agents expose usage differently (or not at
all); when no such signal is available, do not fabricate a percentage —
treat usage as UNKNOWN and default to CAUTION rather than SAFE.

## Instructions

Whenever you receive a large coding task:
1. Output your estimated `Execution Mode` and a quick priority list before writing code.
2. If in `LIMITED` or `CRITICAL` mode, only modify files necessary for P0/P1.
3. Once the safe work is done, create a `goldenboy_checkpoint.md` artifact listing the deferred tasks and stop execution.

## Closing the loop: reporting what actually happened

Golden Boy does not observe your work itself — it only sees what you report
back. After finishing (or abandoning) a task you ran `goldenboy analyze` on,
report the real outcome with `goldenboy report`, echoing back the
`estimated_cost_percentage` from that `analyze` call so Golden Boy can later
compare estimate against reality (`goldenboy calibrate`):

```
goldenboy report --outcome completed \
  --verification-status VERIFIED \
  --task-type bug_fix \
  --estimated-cost-percentage 12.0 \
  --actual-total-tokens 18000 \
  --tests-run 4 --tests-passed 4
```

- `--outcome` is the only required field (`completed` / `failed` / `partial`).
  Every other field is optional — report what you actually know; do not
  invent a number for a field you can't measure (e.g. omit `--tests-run` if
  you didn't run tests, rather than reporting 0).
- `--verification-status VERIFIED` means the outcome is backed by real,
  collected evidence (e.g. an actual test-run exit code you saw) — not the
  same as `--outcome completed`, which only means the work was attempted to
  completion. Use `UNVERIFIED` if you completed the work but did not verify
  it, and `PARTIALLY_VERIFIED` / `FAILED` as appropriate. See "Verification
  vs. completion" below.
- This never sends your prompt or code — only counts and labels (see
  `goldenboy/core/telemetry.py`).
- Golden Boy's own history/analytics/replay improve only as real reports
  like this accumulate; skipping this step means the next `goldenboy
  calibrate` still reports N/A / insufficient data, honestly.

## Verification vs. completion

Do not represent a task as done merely because your execution path
returned without an exception. Distinguish, in your own summary to the
user and in `--verification-status`:
- **Completed but unverified**: you wrote the change but did not run
  tests/build/lint to confirm it. Report `UNVERIFIED`.
- **Completed and verified**: you actually ran the check (tests, build,
  lint) and saw it pass. Report `VERIFIED`, and pass `--tests-run`/
  `--tests-passed`/`--tests-failed` if applicable.
- **Partially verified**: some but not all of the claimed change was
  checked. Report `PARTIALLY_VERIFIED`.
- Never claim verification you didn't perform — an unverified claim of
  success reported as `VERIFIED` corrupts the very data
  `goldenboy calibrate` and `goldenboy replay` rely on.

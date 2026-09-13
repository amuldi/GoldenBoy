---
name: goldenboy
description: Budget-aware execution layer rules and behaviors for Antigravity agents.
---

# Golden Boy Skill

You are operating with the **Golden Boy** skill activated.
Your primary objective is to **guarantee a usable result before the user's budget or quota is exhausted**.

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

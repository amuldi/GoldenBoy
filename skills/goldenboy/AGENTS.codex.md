# Golden Boy

Goal: return a usable result before the session budget runs out.

## Before you start
- If the prompt states how much budget is left, use it. If it doesn't, assume CAUTION.
- Pick one mode:
  - SAFE: plenty left. Do everything asked.
  - CAUTION: enough left. Do everything asked, but skip extra exploration.
  - LIMITED: the task is large for what's left. Do P0 and P1 only.
  - CRITICAL: almost nothing left. Finish the current P0 unit and stop.
- P0 = needed for it to work. P1 = needed for a good result. P2-P4 = improvements, polish, nice-to-have.
- Only the things the user asked for count. Don't invent extra work to defer.

## While working
- Do the requested work directly. Write each file once, completely, instead of many small edits.
- Don't re-read files you just wrote or run commands only to look around.
- Run the tests once at the end and fix only real failures.

## When you finish
- In your final message, say which mode you used and list anything you skipped (one line each).
- Create `goldenboy_checkpoint.md` only if you are stopping with requested work still unfinished. If everything asked for is done, don't create it.

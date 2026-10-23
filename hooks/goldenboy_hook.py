#!/usr/bin/env python3
"""Claude Code `UserPromptSubmit` hook: runs `goldenboy analyze` on the prompt
and injects the task type / complexity / estimated cost as extra context, so
the skill's analysis no longer depends on the model remembering to run it.

Advisory and fail-open: any error (goldenboy missing, bad JSON, timeout)
exits 0 with no output, so a broken hook can never block a prompt. The
prompt is passed to the local CLI only; nothing leaves the machine.

Budget is not known to a hook, so `analyze` runs at its default; the model
must still read the real remaining-usage figure itself (see SKILL.md).
"""
import json
import subprocess
import sys

MIN_PROMPT_CHARS = 40  # skip chit-chat; only analyze task-sized prompts
TIMEOUT_SECONDS = 10


def build_context(prompt: str) -> str:
    """Return the context string for `prompt`, or "" when there is nothing to add."""
    if len(prompt.strip()) < MIN_PROMPT_CHARS:
        return ""
    proc = subprocess.run(
        [sys.executable, "-m", "goldenboy.cli", "analyze", prompt, "--json", "--quiet"],
        capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        return ""
    task = json.loads(proc.stdout)["task"]
    return (
        "[Golden Boy] task_type={task_type} complexity={complexity_label} "
        "estimated_cost={estimated_cost_percentage}% of budget. "
        "Pick your execution mode from the real remaining usage; when done, run "
        "`goldenboy report --outcome ... --estimated-cost-percentage {estimated_cost_percentage}`."
    ).format(**task)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        context = build_context(event.get("prompt", ""))
    except Exception:
        return 0
    if context:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

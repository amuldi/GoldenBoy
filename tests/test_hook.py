import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "goldenboy_hook.py"


def _load():
    spec = importlib.util.spec_from_file_location("goldenboy_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_hook(stdin_text):
    return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True)


def test_task_sized_prompt_gets_context():
    out = _run_hook(json.dumps({"prompt": "refactor the auth module across all services and add tests"}))
    assert out.returncode == 0
    ctx = json.loads(out.stdout)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "UserPromptSubmit"
    assert "task_type=refactor" in ctx["additionalContext"]


def test_short_prompt_adds_nothing():
    out = _run_hook(json.dumps({"prompt": "thanks"}))
    assert out.returncode == 0 and out.stdout == ""


def test_malformed_input_fails_open():
    out = _run_hook("not json")
    assert out.returncode == 0 and out.stdout == ""


def test_cli_failure_fails_open(monkeypatch):
    module = _load()
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", ""))
    assert module.build_context("x" * 60) == ""

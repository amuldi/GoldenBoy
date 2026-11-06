#!/usr/bin/env python3
"""Aggregate real agent-reported token usage from an A/B run directory.

Expects directories named ``r<run>_<tool>_<arm>`` (tool: claude|codex|copilot,
arm: base|skill), each holding the raw output of one headless agent run:

  claude   out.json   (`claude -p --output-format json`; `usage` + `total_cost_usd`)
  codex    out.jsonl  (`codex exec --json`; `turn.completed.usage`)
  copilot  out.jsonl  (`copilot -p --output-format json`; last `session.usage_checkpoint`)

These are the same per-session usage figures the agents write to their own
session logs (what Token Shark reads), not estimates. Nothing is invented: a
run with no readable usage is reported as missing and excluded.

Normalised fields per run:
  output       tokens the model generated
  fresh_input  prompt tokens not served from cache (incl. cache writes)
  cached_input prompt tokens served from cache
  total        fresh_input + cached_input + output
"""
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

_DIR = re.compile(r"^r(\d+)_(claude|codex|copilot)_(base|skill)$")
_INSTRUCTION_FILES = {"err.txt", "CLAUDE.md", "AGENTS.md", "copilot-instructions.md"}


def _claude(path: Path) -> Optional[Dict[str, float]]:
    data = json.loads((path / "out.json").read_text())
    u = data.get("usage")
    if not u:
        return None
    fresh = u["input_tokens"] + u.get("cache_creation_input_tokens", 0)
    cached = u.get("cache_read_input_tokens", 0)
    return {"output": u["output_tokens"], "fresh_input": fresh, "cached_input": cached,
            "turns": data.get("num_turns", 0), "cost_usd": data.get("total_cost_usd")}


def _codex(path: Path) -> Optional[Dict[str, float]]:
    out = fresh = cached = turns = 0
    for line in (path / "out.jsonl").read_text().splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "turn.completed" and ev.get("usage"):
            u = ev["usage"]
            cached += u.get("cached_input_tokens", 0)
            fresh += u["input_tokens"] - u.get("cached_input_tokens", 0)
            out += u["output_tokens"]
            turns += 1
    return {"output": out, "fresh_input": fresh, "cached_input": cached, "turns": turns} if turns else None


def _copilot(path: Path) -> Optional[Dict[str, float]]:
    best = None
    for line in (path / "out.jsonl").read_text().splitlines():
        if "accountingSnapshot" not in line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        metrics = ev.get("data", {}).get("accountingSnapshot", {}).get("modelMetrics")
        if metrics:
            best = metrics  # cumulative snapshot; keep the last one
    if not best:
        return None
    out = fresh = cached = 0
    for m in best.values():
        u = m.get("usage", m)
        cache_read = u.get("cacheReadTokens", 0)
        out += u["outputTokens"]
        cached += cache_read
        fresh += u["inputTokens"] - cache_read  # inputTokens includes cache reads
    return {"output": out, "fresh_input": fresh, "cached_input": cached}


_PARSERS = {"claude": _claude, "codex": _codex, "copilot": _copilot}


def collect(root: Path) -> List[dict]:
    rows = []
    for d in sorted(root.iterdir()):
        m = _DIR.match(d.name)
        if not m or not d.is_dir():
            continue
        run, tool, arm = int(m.group(1)), m.group(2), m.group(3)
        try:
            usage = _PARSERS[tool](d)
        except (OSError, KeyError, ValueError):
            usage = None
        if usage is None:
            rows.append({"run": run, "tool": tool, "arm": arm, "missing": True})
            continue
        usage["total"] = usage["output"] + usage["fresh_input"] + usage["cached_input"]
        files = [p.name for p in d.rglob("*")
                 if p.is_file() and p.suffix in {".py", ".md", ".txt"}
                 and p.name not in _INSTRUCTION_FILES
                 and "logs" not in p.parts and "__pycache__" not in p.parts]
        rows.append({"run": run, "tool": tool, "arm": arm, "deliverables": sorted(files), **usage})
    return rows


def summarise(rows: List[dict]) -> Dict[str, dict]:
    summary: Dict[str, dict] = {}
    for tool in ("claude", "codex", "copilot"):
        entry: dict = {}
        for arm in ("base", "skill"):
            ok = [r for r in rows if r["tool"] == tool and r["arm"] == arm and not r.get("missing")]
            if not ok:
                continue
            entry[arm] = {"n": len(ok)}
            for key in ("output", "fresh_input", "cached_input", "total"):
                vals = [r[key] for r in ok]
                entry[arm][key] = {"mean": statistics.mean(vals), "min": min(vals), "max": max(vals)}
            entry[arm]["deliverables"] = statistics.mean(len(r["deliverables"]) for r in ok)
        if "base" in entry and "skill" in entry:
            for key in ("output", "fresh_input", "total"):
                b, s = entry["base"][key]["mean"], entry["skill"][key]["mean"]
                entry[f"{key}_change_pct"] = round((s - b) / b * 100.0, 1) if b else None
        summary[tool] = entry
    return summary


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print("usage: collect_token_benchmark.py <runs-dir> <out.json>", file=sys.stderr)
        return 2
    rows = collect(Path(argv[1]))
    result = {"runs": rows, "summary": summarise(rows)}
    Path(argv[2]).write_text(json.dumps(result, indent=2))
    for tool, e in result["summary"].items():
        if "total_change_pct" in e:
            print(f"{tool:8} total {e['total_change_pct']:+.1f}%  output {e['output_change_pct']:+.1f}%  "
                  f"fresh_in {e['fresh_input_change_pct']:+.1f}%  (n={e['base']['n']}/{e['skill']['n']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

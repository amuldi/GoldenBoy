"""Deterministic task-complexity scoring, independent of repository size and
independent of estimated cost.

Before this module existed, `TaskProfile.complexity` was back-computed from
`Estimator`'s cost percentage (`min(1.0, estimated_percentage / 100.0)`) --
documented at the time as a deliberate choice to avoid inventing "a second,
separately-invented complexity number" (see `decision_engine.py`'s prior
module docstring). That reasoning held only as long as there was no real,
independent complexity signal to reuse instead. Now there is one: this
module scores task *text* directly (keyword/structural signals), and
`Estimator.estimate_task()` feeds that score into its own cost formula
(the output-size multiplier), rather than the other way around. See
ARCHITECTURE_AUDIT.md and CHANGELOG.md for the before/after evidence.

Explicitly a heuristic keyword/structure score in [0, 1], NOT a calibrated
probability -- same convention as `TaskClassifier`'s confidence (see that
module's docstring). A score of 0.72 means "this task matched signals
totaling 0.72 of the fixed weight table below," nothing more.
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple

# (signal name, phrases that trigger it, fixed weight). Weights are additive
# and the total is clamped to 1.0 -- a fixed, documented table, not a
# trained/tuned model. Ordered roughly by how much scope/blast-radius the
# signal implies.
_SIGNAL_KEYWORDS: List[Tuple[str, List[str], float]] = [
    ("architecture_keyword",
     ["architecture", "redesign", "re-architect", "system design", "new service", "microservice"],
     0.30),
    ("migration_keyword",
     ["migrate", "migration", "rewrite", "data model"],
     0.25),
    ("cross_module_keyword",
     ["across the", "across all", "throughout the", "end-to-end", "end to end",
      "multiple modules", "multiple files", "multiple services"],
     0.20),
    ("api_change_keyword",
     ["api", "endpoint", "interface change", "breaking change", "schema change"],
     0.15),
    ("dependency_change_keyword",
     ["dependency", "dependencies", "upgrade", "package.json", "pyproject.toml",
      "requirements.txt", "lockfile"],
     0.10),
    ("test_requirement_keyword",
     ["test", "tests", "testing", "coverage"],
     0.10),
    ("refactor_keyword",
     ["refactor", "restructure", "reorganize", "de-duplicate", "deduplicate"],
     0.10),
]

# Below this many non-empty clauses (split on "and"/comma/semicolon), the
# prompt reads as a single ask; at or above it, the prompt is asking for
# several distinct things in one task -- a real scope signal independent of
# any keyword match.
_MULTI_STEP_CLAUSE_THRESHOLD = 3
_MULTI_STEP_WEIGHT = 0.15

_CLAUSE_SPLIT = re.compile(r"\band\b|,|;", re.IGNORECASE)

# A real task description is realistically a few sentences to a few
# paragraphs -- at most a few thousand characters. Scoring beyond this
# prefix would mean repeatedly regex-scanning an amount of text no real
# task prompt reaches; without this bound, a pathologically large prompt
# (e.g. an entire file pasted in) made every phrase/clause regex pass over
# it in full, measured at ~9s for a 25M-character prompt versus ~0.01s
# with this bound in place (see CHANGELOG.md).
_MAX_SCAN_CHARS = 20_000


@dataclass
class TaskComplexity:
    score: float  # heuristic weighted-signal strength in [0, 1] -- NOT a calibrated probability
    signals: List[str] = field(default_factory=list)


def _clause_count(task_text: str) -> int:
    return len([p for p in _CLAUSE_SPLIT.split(task_text) if p.strip()])


def estimate_task_complexity(task_text: str) -> TaskComplexity:
    """Score `task_text` against the fixed signal table above. Empty/blank
    text scores 0.0 with no signals -- there is nothing to match."""
    if not task_text or not task_text.strip():
        return TaskComplexity(score=0.0, signals=[])

    bounded_text = task_text[:_MAX_SCAN_CHARS]
    lowered = bounded_text.lower()
    signals: List[str] = []
    raw = 0.0

    for name, phrases, weight in _SIGNAL_KEYWORDS:
        if any(re.search(r"\b" + re.escape(phrase) + r"\b", lowered) for phrase in phrases):
            signals.append(name)
            raw += weight

    if _clause_count(bounded_text) >= _MULTI_STEP_CLAUSE_THRESHOLD:
        signals.append("multi_step_scope")
        raw += _MULTI_STEP_WEIGHT

    return TaskComplexity(score=min(1.0, raw), signals=signals)

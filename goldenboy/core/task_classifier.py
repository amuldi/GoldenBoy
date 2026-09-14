"""Deterministic task-type classification from prompt text.

This is a keyword/heuristic classifier, not a trained model -- there is no
labeled dataset of real Golden Boy tasks to train one on yet (see
docs/DATASETS.md). Per the project's engineering philosophy ("start with a
deterministic baseline, only then consider ML"), this is the honest first
step: transparent, deterministic, and testable, with a confidence score
that reflects keyword-match strength -- explicitly *not* a calibrated
probability. Replace or augment with a learned model only once real,
labeled outcome data exists (see `goldenboy.core.history`).
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from goldenboy.core.task_types import TaskType

# (task type) -> [(keyword/phrase, weight), ...]. Weights are deliberately
# coarse (1-3): this is a heuristic ranking signal, not a tuned model, and
# implying more precision than that would misrepresent it. Longer, more
# specific phrases are weighted higher than single common words so e.g.
# "fix a bug" outranks a bare "fix" appearing incidentally in a refactor
# description.
_KEYWORDS: Dict[TaskType, List[Tuple[str, int]]] = {
    TaskType.BUG_FIX: [
        ("fix a bug", 3), ("bug fix", 3), ("bugfix", 3), ("hotfix", 3),
        ("fix the bug", 3), ("fix an issue", 2), ("regression", 2),
        ("broken", 2), ("crash", 2), ("crashing", 2), ("fails", 1), ("failing", 1),
        ("error", 1), ("bug", 2), ("fix", 1), ("incorrect", 1), ("wrong", 1),
    ],
    TaskType.REFACTOR: [
        ("refactor", 3), ("restructure", 2), ("clean up", 2), ("cleanup", 2),
        ("simplify", 2), ("extract method", 2), ("extract function", 2),
        ("rename", 1), ("reorganize", 2), ("de-duplicate", 2), ("deduplicate", 2),
        ("consolidate", 1), ("modernize", 1),
    ],
    TaskType.TESTING: [
        ("write tests", 3), ("add tests", 3), ("unit test", 3), ("test coverage", 3),
        ("integration test", 3), ("write a test", 2), ("regression test", 2),
        ("test suite", 2), ("pytest", 1), ("assert", 1), ("mock", 1), ("fixture", 1),
        ("tests", 1), ("test", 1),
    ],
    TaskType.DEBUGGING: [
        ("debug", 3), ("investigate", 2), ("diagnose", 2), ("root cause", 3),
        ("why is", 2), ("track down", 2), ("reproduce the issue", 2),
        ("stack trace", 2), ("traceback", 2), ("flaky", 2), ("intermittent", 2),
    ],
    TaskType.DOCUMENTATION: [
        ("documentation", 3), ("document", 2), ("readme", 3), ("docstring", 2),
        ("changelog", 2), ("write docs", 3), ("update docs", 3), ("comment", 1),
        ("explain", 1), ("tutorial", 2), ("guide", 1),
    ],
    TaskType.RESEARCH: [
        ("research", 3), ("investigate options", 2), ("compare", 1), ("evaluate", 2),
        ("feasibility", 2), ("explore", 2), ("survey", 2), ("benchmark options", 2),
        ("what are the tradeoffs", 2), ("tradeoffs", 1), ("spike", 2), ("prototype", 2),
    ],
    TaskType.DEPENDENCY_CHANGE: [
        ("upgrade dependency", 3), ("upgrade dependencies", 3), ("bump version", 2),
        ("update package", 2), ("update packages", 2), ("dependency", 2),
        ("dependencies", 2), ("package.json", 2), ("pyproject.toml", 2),
        ("requirements.txt", 2), ("lockfile", 2), ("cve", 2), ("vulnerable dependency", 3),
    ],
    TaskType.ARCHITECTURE_CHANGE: [
        ("architecture", 3), ("redesign", 3), ("re-architect", 3), ("system design", 2),
        ("migrate to", 2), ("migration", 2), ("rewrite", 2), ("new service", 2),
        ("microservice", 2), ("data model", 1), ("schema change", 2),
        ("authentication system", 2), ("auth system", 2),
    ],
    TaskType.CODE_REVIEW: [
        ("code review", 3), ("review this", 2), ("review the", 2), ("pr feedback", 2),
        ("review pr", 3), ("pull request review", 3), ("address review comments", 3),
        ("lgtm", 1), ("nitpick", 1),
    ],
    TaskType.PERFORMANCE_OPTIMIZATION: [
        ("optimize", 3), ("performance", 3), ("speed up", 3), ("latency", 2),
        ("throughput", 2), ("slow", 2), ("bottleneck", 2), ("memory usage", 2),
        ("reduce allocations", 2), ("cache", 1), ("profiling", 2), ("profile", 1),
    ],
    TaskType.RELEASE: [
        ("release", 3), ("cut a release", 3), ("bump version", 2), ("changelog", 1),
        ("publish", 2), ("ship v", 2), ("tag release", 3), ("version bump", 2),
        ("deploy", 2), ("deployment", 2),
    ],
    TaskType.IMPLEMENTATION: [
        ("implement", 3), ("add a feature", 3), ("add feature", 3), ("build a", 2),
        ("build an", 2), ("create a", 2), ("create an", 2), ("new endpoint", 2),
        ("new feature", 3), ("support for", 2), ("add support", 2), ("integrate", 2),
    ],
}

# Compiled once at import time: (task type, compiled pattern, weight). The
# trailing `s?` before the boundary is a deliberately simple plural
# tolerance (test/tests, bug/bugs, crash/crashes-via-"crash"+s stays
# unmatched -- this is not full stemming, just the common regular-plural
# case) so "add unit tests" matches the same entry as "add a unit test"
# without doubling every phrase in the table by hand.
_COMPILED: List[Tuple[TaskType, "re.Pattern[str]", int]] = [
    (task_type, re.compile(r"\b" + re.escape(phrase) + r"s?\b", re.IGNORECASE), weight)
    for task_type, phrases in _KEYWORDS.items()
    for phrase, weight in phrases
]


@dataclass
class TaskClassification:
    task_type: TaskType
    confidence: float  # heuristic match-strength in [0, 1] -- not a calibrated probability
    signals: Dict[str, int] = field(default_factory=dict)  # matched-phrase -> weight, for transparency


class TaskClassifier:
    """Scores prompt text against a fixed keyword table per `TaskType` and
    returns the highest-scoring type with a heuristic confidence.

    Deliberately simple: this is meant to be replaced (or blended with) a
    real model once labeled outcome data exists via `HistoryStore`, not to
    be the permanent state of the art. See the module docstring.
    """

    def classify(self, task_text: str) -> TaskClassification:
        if not task_text or not task_text.strip():
            return TaskClassification(task_type=TaskType.UNKNOWN, confidence=0.0, signals={})

        scores: Dict[TaskType, int] = {t: 0 for t in TaskType if t != TaskType.UNKNOWN}
        signals: Dict[str, int] = {}

        for task_type, pattern, weight in _COMPILED:
            matches = pattern.findall(task_text)
            if matches:
                scores[task_type] += weight * len(matches)
                signals[f"{task_type.value}:{pattern.pattern}"] = weight * len(matches)

        total = sum(scores.values())
        if total == 0:
            return TaskClassification(task_type=TaskType.UNKNOWN, confidence=0.0, signals={})

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_type, top_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0

        # Confidence reflects how dominant the top match is relative to
        # everything else that matched, not an absolute keyword count --
        # a prompt that only ever matches one category should read as
        # confident even if it only hit a couple of keywords.
        margin = (top_score - runner_up_score) / total
        coverage = min(1.0, top_score / 6.0)  # softly reward a few strong matches over one weak one
        confidence = round(min(1.0, 0.5 * margin + 0.5 * coverage + 0.15), 3)

        return TaskClassification(task_type=top_type, confidence=confidence, signals=signals)

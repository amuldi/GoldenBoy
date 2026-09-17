import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from goldenboy.core.complexity import estimate_task_complexity
from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.priorities import ExecutionUnit

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

# Directories that are never source-of-truth "codebase" for context-size
# purposes: dependency trees, VCS internals, and build/cache output. Left
# unfiltered, a single local virtualenv or node_modules can outweigh the
# actual project by 100x and swamp the estimate (see estimator tests).
_EXCLUDED_DIR_NAMES = {
    "venv", "venv2", ".venv", "env", ".env",
    "node_modules", ".git", "__pycache__", ".pytest_cache",
    "dist", "build", ".mypy_cache", ".ruff_cache", "site-packages",
    ".goldenboy", ".tox", "egg-info",
}
_SOURCE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx")
_MAX_SCAN_FILES = 200
_MAX_FILE_BYTES = 200_000  # skip pathologically large single files (e.g. bundled/minified output)

# --- Context relevance (see ARCHITECTURE_AUDIT.md / CHANGELOG.md: "cost
# estimate dominated by repo size, not task size") ---------------------------
#
# `_estimate_codebase_context` (below, unchanged) answers "how big is this
# repository" -- a near-constant per repo, regardless of the task. It is
# reported for transparency but no longer fed into the cost total on its
# own. `_estimate_relevant_context` answers a different question: "which
# files, if any, does *this task's wording* actually point at" -- and only
# that (bounded, possibly empty) subset feeds the cost formula.
#
# Common English function words and generic task verbs, excluded so they
# never drive a false-positive path match (a directory is essentially never
# named "the" or "fix"; one very occasionally is named after a real noun
# like "bug" or "api", which is exactly what should still match).
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
    "had", "was", "her", "his", "its", "our", "out", "use", "get", "put",
    "run", "let", "how", "why", "who", "what", "when", "where", "which",
    "this", "that", "with", "from", "into", "onto", "have", "will",
    "your", "their", "there", "about", "across", "after", "before",
    "while", "than", "then", "them", "they", "some", "such", "only",
    "also", "each", "both", "more", "most", "other", "over", "under",
    "again", "once", "fix", "add", "new", "update", "write", "create",
    "implement", "build", "make", "remove", "delete", "change", "modify",
    "improve", "review", "refactor",
}
_WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")
_TEST_MENTION_PATTERN = re.compile(r"\btest(s|ing)?\b", re.IGNORECASE)

# Same bound and rationale as `goldenboy.core.complexity._MAX_SCAN_CHARS`:
# a real task description is realistically a few thousand characters at
# most; without this, a pathologically large prompt made keyword
# extraction scan it in full for no benefit (see CHANGELOG.md).
_MAX_TASK_TEXT_SCAN_CHARS = 20_000

# Fixed, documented weights for `_score_file_relevance` -- a keyword actually
# appearing in the file's path is the strongest signal; test-file
# association and recent-modification are secondary corroborating signals,
# not standalone qualifiers (a file with only a recency match and no keyword
# or test association scores 0 and is never selected).
_KEYWORD_PATH_WEIGHT = 3
_TEST_ASSOCIATION_WEIGHT = 2
_RECENCY_WEIGHT = 1
_RECENCY_WINDOW_SECONDS = 30 * 86400  # 30 days

# Expected-output-size multiplier on prompt tokens, scaled linearly by
# `TaskComplexity.score` (0.0 -> _OUTPUT_MULTIPLIER_MIN, 1.0 ->
# _OUTPUT_MULTIPLIER_MAX). Replaces the old fixed `prompt_tokens * 3`: a
# one-line typo fix and a cross-module migration described in a
# similarly-sized prompt should not produce the same expected-output
# estimate. Fixed, documented constants -- not fit to any data.
_OUTPUT_MULTIPLIER_MIN = 1.5
_OUTPUT_MULTIPLIER_MAX = 5.0

# Verification overhead (tests/lint/diff review) as a fraction of
# (prompt + expected output) tokens. Fixed, documented constant -- a rough,
# labeled approximation, not a measured per-task figure.
_VERIFICATION_FRACTION = 0.15


def _extract_keywords(task_text: str) -> List[str]:
    """Lowercased, deduplicated, order-preserving content words from
    `task_text` (length >= 3, stopwords removed) -- the vocabulary
    `_score_file_relevance` matches against file paths."""
    seen: List[str] = []
    for match in _WORD_PATTERN.finditer(task_text[:_MAX_TASK_TEXT_SCAN_CHARS].lower()):
        word = match.group(0)
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
    return seen


def _score_file_relevance(
    path: str, keywords: List[str], mentions_tests: bool, now: float
) -> int:
    """Deterministic relevance score for one file path against `keywords`
    extracted from the task text. Returns 0 for "no evidence this file is
    relevant" -- callers must not include zero-scored files."""
    lowered = path.lower()
    score = 0
    if any(kw in lowered for kw in keywords):
        score += _KEYWORD_PATH_WEIGHT
    if mentions_tests and "test" in lowered:
        score += _TEST_ASSOCIATION_WEIGHT
    if score > 0:
        try:
            if now - os.path.getmtime(path) <= _RECENCY_WINDOW_SECONDS:
                score += _RECENCY_WEIGHT
        except OSError:
            pass
    return score


@dataclass
class TaskEstimate:
    estimated_percentage: float
    confidence: float  # 0.0 to 1.0
    # Everything below is an explanatory breakdown of how the two fields
    # above were derived -- defaulted so existing callers that only ever
    # set the two fields above (tests, `estimate_plan`, `RiskEngine`
    # call sites) are unaffected. See `Estimator.estimate_task`.
    repository_tokens: int = 0
    relevant_context_tokens: int = 0
    relevant_file_count: int = 0
    prompt_tokens: int = 0
    estimated_output_tokens: int = 0
    verification_tokens: int = 0
    complexity_score: float = 0.0
    complexity_signals: List[str] = field(default_factory=list)

class Estimator:
    """Estimates the required budget for tasks by analyzing prompt tokens and repository size."""

    def __init__(
        self,
        base_cost_per_unit: Optional[float] = None,
        max_budget_tokens: Optional[int] = None,
        config: Optional[GoldenBoyConfig] = None,
    ):
        self.config = config or get_default_config()
        self.base_cost_per_unit = (
            base_cost_per_unit if base_cost_per_unit is not None else self.config.base_cost_per_unit
        )
        self.max_budget_tokens = (
            max_budget_tokens if max_budget_tokens is not None else self.config.max_budget_tokens
        )
        if HAS_TIKTOKEN:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        if HAS_TIKTOKEN:
            return len(self.encoding.encode(text))
        # Fallback: ~4 characters/token, the standard rough estimate for
        # English text (used e.g. in OpenAI's own docs) when no real
        # tokenizer is available. Deliberately *not* a word-count heuristic
        # (len(text.split()) * k): two prompts with the same word count but
        # different content -- e.g. "Fix a typo in README" and "Implement
        # OAuth authentication with tests" are both 5 words -- would
        # otherwise produce identical estimates regardless of actual
        # length/complexity, which defeats the point of estimating from the
        # task text at all. Confidence is still reported lower than the
        # tiktoken path (see estimate_task) to reflect that this is coarser.
        return max(1, len(text) // 4) if text else 0

    def _iter_source_files(self, directory: str):
        """Yield source file paths under `directory`, pruning known non-source
        directories (dependencies, VCS, caches, build output) so they never
        get walked at all, rather than filtering them out after the fact."""
        for root, dirnames, filenames in os.walk(directory):
            dirnames[:] = [
                d for d in dirnames if d not in _EXCLUDED_DIR_NAMES and not d.endswith(".egg-info")
            ]
            for name in filenames:
                if name.endswith(_SOURCE_EXTENSIONS):
                    yield os.path.join(root, name)

    def _estimate_codebase_context(self, directory: str = ".") -> int:
        """Estimates token footprint of the current codebase.

        This is a rough heuristic, not an exact context size: it sums
        tokens across up to `_MAX_SCAN_FILES` source files (skipping
        dependency/build/VCS directories and unusually large files) and
        makes no attempt to model what an agent would actually load into
        context for a given task. Treat the result as ESTIMATED, never EXACT.
        """
        total_tokens = 0
        scanned = 0
        for path in self._iter_source_files(directory):
            if scanned >= _MAX_SCAN_FILES:
                break
            try:
                if os.path.getsize(path) > _MAX_FILE_BYTES:
                    continue
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                total_tokens += self._count_tokens(content)
                scanned += 1
            except OSError:
                pass
        return total_tokens

    def _estimate_relevant_context(self, task_text: str, directory: str = ".") -> Tuple[int, int]:
        """Returns `(relevant_context_tokens, relevant_file_count)`: the
        token total and file count of only the source files whose *path*
        the task text actually gives evidence for (see
        `_score_file_relevance`), bounded to the `_MAX_SCAN_FILES` highest-
        scoring files.

        If the task text yields no keywords, or no file scores above 0,
        this returns `(0, 0)` -- deliberately, not a fallback scan of
        everything. Golden Boy genuinely does not know what is relevant in
        that case, and reporting a real repo-sized number would misrepresent
        that as knowledge it doesn't have (see module docstring / P0
        finding in ARCHITECTURE_AUDIT.md). `Estimator.estimate_task` lowers
        its reported confidence when this returns zero, rather than
        silently guessing.
        """
        keywords = _extract_keywords(task_text)
        if not keywords:
            return 0, 0

        mentions_tests = bool(_TEST_MENTION_PATTERN.search(task_text[:_MAX_TASK_TEXT_SCAN_CHARS]))
        now = time.time()

        scored: List[Tuple[int, str]] = []
        for path in self._iter_source_files(directory):
            score = _score_file_relevance(path, keywords, mentions_tests, now)
            if score > 0:
                scored.append((score, path))

        if not scored:
            return 0, 0

        # Highest score first; path as a tiebreaker so selection (and thus
        # the resulting token count) is deterministic across runs.
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        selected = scored[:_MAX_SCAN_FILES]

        total_tokens = 0
        counted = 0
        for _, path in selected:
            try:
                if os.path.getsize(path) > _MAX_FILE_BYTES:
                    continue
                with open(path, "r", encoding="utf-8") as file:
                    total_tokens += self._count_tokens(file.read())
                counted += 1
            except OSError:
                pass
        return total_tokens, counted

    def estimate_task(self, prompt: str, directory: str = ".") -> TaskEstimate:
        """Estimate the overall task cost from four independent,
        individually-inspectable terms:

            total = relevant_context + prompt + expected_output + verification

        `relevant_context` is *not* the whole repository (see
        `_estimate_relevant_context`) -- that decoupling is the fix for the
        P0 finding in ARCHITECTURE_AUDIT.md ("cost estimate dominated by
        repo size, not task size"). `repository_tokens` (whole-repo size)
        is still computed and reported on the returned `TaskEstimate` for
        transparency/comparison, but no longer feeds the cost total itself.

        `expected_output` scales with `complexity_score` (from
        `goldenboy.core.complexity`, an independent signal derived from the
        task text) rather than a single fixed 3x multiplier -- a task with
        architecture/migration/cross-module signals is expected to produce
        more output per prompt token than a small, localized one.
        """
        prompt_tokens = self._count_tokens(prompt)
        repository_tokens = self._estimate_codebase_context(directory)
        relevant_tokens, relevant_file_count = self._estimate_relevant_context(prompt, directory)
        complexity = estimate_task_complexity(prompt)

        output_multiplier = _OUTPUT_MULTIPLIER_MIN + (
            _OUTPUT_MULTIPLIER_MAX - _OUTPUT_MULTIPLIER_MIN
        ) * complexity.score
        estimated_output_tokens = round(prompt_tokens * output_multiplier)
        # Verification overhead (running/reading tests, lint, review of the
        # diff) modeled as a fixed fraction of what was just written and
        # read -- a real, separately-named term (per the project brief's
        # "Total = Context + Task + Execution + Verification" framing)
        # rather than folded silently into the output multiplier.
        verification_tokens = round(
            (prompt_tokens + estimated_output_tokens) * _VERIFICATION_FRACTION
        )

        total_estimated_tokens = (
            relevant_tokens + prompt_tokens + estimated_output_tokens + verification_tokens
        )

        estimated_percentage = (total_estimated_tokens / self.max_budget_tokens) * 100.0
        # Floor at 5%: even a trivial prompt has nonzero planning/verification
        # overhead, so a 0% estimate would be misleadingly precise.
        estimated_percentage = min(100.0, max(5.0, estimated_percentage))

        base_confidence = 0.85 if HAS_TIKTOKEN else 0.50
        # No file-path evidence of what's relevant is a real drop in how
        # much to trust this estimate -- not a fabricated precision penalty,
        # but a direct consequence of relevant_file_count being the thing
        # that grounds relevant_tokens at all.
        confidence = base_confidence if relevant_file_count > 0 else round(base_confidence * 0.7, 3)

        return TaskEstimate(
            estimated_percentage=estimated_percentage,
            confidence=confidence,
            repository_tokens=repository_tokens,
            relevant_context_tokens=relevant_tokens,
            relevant_file_count=relevant_file_count,
            prompt_tokens=prompt_tokens,
            estimated_output_tokens=estimated_output_tokens,
            verification_tokens=verification_tokens,
            complexity_score=complexity.score,
            complexity_signals=complexity.signals,
        )

    def estimate_plan(self, plan: List[ExecutionUnit]) -> TaskEstimate:
        """Estimate cost based on a concrete execution plan."""
        total_cost = sum(unit.estimated_cost for unit in plan if unit.status == "pending")
        if total_cost == 0:
            # Fallback if units have no explicit cost
            total_cost = len([u for u in plan if u.status == "pending"]) * self.base_cost_per_unit
            
        return TaskEstimate(
            estimated_percentage=total_cost,
            confidence=0.90 if HAS_TIKTOKEN else 0.60
        )

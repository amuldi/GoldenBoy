import os
from dataclasses import dataclass
from typing import List, Optional

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

@dataclass
class TaskEstimate:
    estimated_percentage: float
    confidence: float  # 0.0 to 1.0

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

    def estimate_task(self, prompt: str) -> TaskEstimate:
        """
        Estimate the overall task cost based on prompt complexity and context.
        """
        prompt_tokens = self._count_tokens(prompt)
        context_tokens = self._estimate_codebase_context()
        
        # Assume an output multiplier based on prompt tokens and context mapping
        estimated_output_tokens = prompt_tokens * 3 
        total_estimated_tokens = context_tokens + prompt_tokens + estimated_output_tokens
        
        estimated_percentage = (total_estimated_tokens / self.max_budget_tokens) * 100.0
        # Floor at 5%: even a trivial prompt has nonzero planning/verification
        # overhead, so a 0% estimate would be misleadingly precise.
        estimated_percentage = min(100.0, max(5.0, estimated_percentage))
        
        confidence = 0.85 if HAS_TIKTOKEN else 0.50
        
        return TaskEstimate(
            estimated_percentage=estimated_percentage,
            confidence=confidence
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

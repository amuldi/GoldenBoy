"""Checkpoint / Rollback for file changes an agent makes, built entirely on
git -- no second version-control system, per the project brief ("if the
current project uses git, use the existing git structure; do not build a
new VCS").

Distinct from `goldenboy.core.checkpoint.CheckpointManager`, which
checkpoints Golden Boy's own *task-plan state* (which `ExecutionUnit`s are
done/deferred) -- this module checkpoints the *working tree*, so an agent's
edits can be verified (typecheck/test/build, whatever commands the caller
supplies) and rolled back if verification fails. Named `snapshot`, not
`checkpoint`, specifically to avoid colliding with that existing, unrelated
concept and its established CLI vocabulary (`goldenboy status`/`resume`
already say "checkpoint" to mean the task-plan one).

How a snapshot works:
    - `create()` records the current commit (`git rev-parse HEAD`) and, if
      the working tree is dirty, a stash-commit object via
      `git stash create` -- which captures the tracked-file diff as a
      normal git commit object *without* touching the working tree, the
      index, or the stash ref list (see `git-stash(1)`: "create" is the
      plumbing form; nothing is applied or removed). If the tree is clean,
      no stash object is needed -- `HEAD` alone already *is* the snapshot.
    - `verify()` runs caller-supplied commands (e.g. `["pytest"]`,
      `["mypy"]`, a build command) in order, stopping at the first failure
      -- it does not know what "typecheck"/"test"/"build" mean for your
      project; you tell it.
    - `rollback()` restores tracked files to their content at snapshot time
      via `git checkout <sha> -- .` -- the least destructive form (moves
      no ref, touches only the working tree).

Known limitation (documented, not silently glossed over): a file that
was *untracked* (never `git add`ed) when the snapshot was taken, and a
file *newly created* after the snapshot, are not restored/removed by
rollback -- `git stash create` and `git checkout <sha> -- .` both operate
on tracked content. Only tracked-file edits are covered.
"""
import json
import os
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from goldenboy.core.errors import SnapshotError

SNAPSHOT_SCHEMA_VERSION = 1

# Read-only tail of a verify step's output kept in the report -- enough to
# see what failed without persisting an unbounded amount of subprocess
# output into `.goldenboy/`.
_OUTPUT_TAIL_CHARS = 4000
_DEFAULT_STEP_TIMEOUT_SECONDS = 600.0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(text: str, limit: int = _OUTPUT_TAIL_CHARS) -> str:
    return text if len(text) <= limit else "…(truncated)…" + text[-limit:]


@dataclass
class Snapshot:
    schema_version: int
    id: str
    label: str
    created_at: str
    head_sha: str
    stash_sha: Optional[str]
    clean: bool  # True if the working tree had nothing to stash at snapshot time

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        return cls(
            schema_version=data["schema_version"],
            id=data["id"],
            label=data["label"],
            created_at=data["created_at"],
            head_sha=data["head_sha"],
            stash_sha=data.get("stash_sha"),
            clean=data["clean"],
        )


@dataclass
class VerifyStepResult:
    command: str
    returncode: Optional[int]
    passed: bool
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    error: Optional[str] = None  # set if the command could not even be started (e.g. not found)

    def render(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        line = f"  [{status}] {self.command} ({self.duration_seconds:.2f}s)"
        if self.error:
            line += f" -- could not run: {self.error}"
        return line


@dataclass
class VerifyResult:
    passed: bool
    steps: List[VerifyStepResult] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"Verification: {'PASS' if self.passed else 'FAIL'}"]
        for step in self.steps:
            lines.append(step.render())
        return "\n".join(lines)


def _run_git(repo_dir: str, args: Sequence[str], check: bool = True) -> "subprocess.CompletedProcess[str]":
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, *args],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as e:
        raise SnapshotError("git is not installed or not on PATH.") from e
    if check and result.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


class SnapshotManager:
    def __init__(self, repo_dir: str = ".", state_dir: str = ".goldenboy", filename: str = "snapshots.jsonl"):
        self.repo_dir = repo_dir
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, filename)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)

    def _ensure_repo(self) -> None:
        result = _run_git(self.repo_dir, ["rev-parse", "--is-inside-work-tree"], check=False)
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise SnapshotError(
                f"'{self.repo_dir}' is not inside a git repository -- snapshots require git "
                "(Golden Boy does not implement its own version control)."
            )

    def create(self, label: str = "") -> Snapshot:
        """Records the current working-tree state. Raises `SnapshotError`
        if `repo_dir` is not a git repository, or has no commits yet
        (`git rev-parse HEAD` needs at least one commit to point to)."""
        self._ensure_repo()
        head = _run_git(self.repo_dir, ["rev-parse", "HEAD"]).stdout.strip()

        stash_result = _run_git(self.repo_dir, ["stash", "create"], check=False)
        stash_sha = stash_result.stdout.strip() or None
        clean = stash_sha is None

        snapshot = Snapshot(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            id=f"{int(time.time() * 1000):x}",
            label=label or "(unlabeled)",
            created_at=_utcnow_iso(),
            head_sha=head,
            stash_sha=stash_sha,
            clean=clean,
        )
        self._append(snapshot)
        return snapshot

    def _append(self, snapshot: Snapshot) -> None:
        self._ensure_dir()
        with open(self.state_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")

    def list(self) -> List[Snapshot]:
        if not os.path.exists(self.state_file):
            return []
        snapshots: List[Snapshot] = []
        with open(self.state_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    snapshots.append(Snapshot.from_dict(json.loads(stripped)))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue  # one corrupted line doesn't invalidate the rest
        return snapshots

    def latest(self) -> Optional[Snapshot]:
        snapshots = self.list()
        return snapshots[-1] if snapshots else None

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        for s in self.list():
            if s.id == snapshot_id:
                return s
        return None

    def verify(
        self,
        commands: List[str],
        timeout: float = _DEFAULT_STEP_TIMEOUT_SECONDS,
        stop_on_failure: bool = True,
    ) -> VerifyResult:
        """Runs each of `commands` (shell-style strings, parsed with
        `shlex.split` into an argv list -- never run through a shell, so
        this is not susceptible to shell-metacharacter injection even
        though the strings originate from the caller's own CLI arguments)
        in `repo_dir`, in order. Stops at the first failure by default."""
        steps: List[VerifyStepResult] = []
        overall_passed = True

        for command in commands:
            try:
                argv = shlex.split(command)
            except ValueError as e:
                steps.append(VerifyStepResult(
                    command=command, returncode=None, passed=False,
                    duration_seconds=0.0, stdout_tail="", stderr_tail="", error=f"could not parse: {e}",
                ))
                overall_passed = False
                if stop_on_failure:
                    break
                continue

            start = time.monotonic()
            try:
                proc = subprocess.run(
                    argv, cwd=self.repo_dir, capture_output=True, text=True,
                    timeout=timeout, check=False,
                )
                duration = time.monotonic() - start
                passed = proc.returncode == 0
                steps.append(VerifyStepResult(
                    command=command, returncode=proc.returncode, passed=passed,
                    duration_seconds=duration, stdout_tail=_tail(proc.stdout), stderr_tail=_tail(proc.stderr),
                ))
            except FileNotFoundError as e:
                steps.append(VerifyStepResult(
                    command=command, returncode=None, passed=False,
                    duration_seconds=time.monotonic() - start, stdout_tail="", stderr_tail="",
                    error=str(e),
                ))
                passed = False
            except subprocess.TimeoutExpired:
                steps.append(VerifyStepResult(
                    command=command, returncode=None, passed=False,
                    duration_seconds=timeout, stdout_tail="", stderr_tail="",
                    error=f"timed out after {timeout}s",
                ))
                passed = False

            if not passed:
                overall_passed = False
                if stop_on_failure:
                    break

        return VerifyResult(passed=overall_passed, steps=steps)

    def rollback(self, snapshot: Optional[Snapshot] = None) -> Snapshot:
        """Restores tracked files to their content at `snapshot` time (or
        the latest recorded snapshot if none given). See module docstring
        for exactly what is and isn't restored."""
        self._ensure_repo()
        target = snapshot or self.latest()
        if target is None:
            raise SnapshotError("No snapshot to roll back to -- call create() first.")

        # Invariant enforced at construction (`create()`): clean is True iff
        # stash_sha is None -- asserted here, not just assumed, so a future
        # change to that invariant fails loudly instead of passing `None`
        # to `git checkout`.
        if target.clean:
            restore_sha = target.head_sha
        else:
            assert target.stash_sha is not None
            restore_sha = target.stash_sha
        _run_git(self.repo_dir, ["checkout", restore_sha, "--", "."])
        return target

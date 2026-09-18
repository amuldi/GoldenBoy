import subprocess

import pytest

from goldenboy.core.errors import SnapshotError
from goldenboy.core.snapshot import SnapshotManager


def _git(repo_dir, *args):
    subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    (repo_dir / "a.py").write_text("print(1)\n")
    _git(repo_dir, "add", "a.py")
    _git(repo_dir, "commit", "-q", "-m", "init")
    return repo_dir


def test_create_requires_a_git_repo(tmp_path):
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    mgr = SnapshotManager(repo_dir=str(not_a_repo), state_dir=str(not_a_repo / ".goldenboy"))
    with pytest.raises(SnapshotError, match="not inside a git repository"):
        mgr.create(label="x")


def test_create_on_clean_tree_records_clean_snapshot(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    snap = mgr.create(label="clean")
    assert snap.clean is True
    assert snap.stash_sha is None
    assert snap.head_sha


def test_create_on_dirty_tree_records_stash_object(repo):
    (repo / "a.py").write_text("print(2)\n")
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    snap = mgr.create(label="dirty")
    assert snap.clean is False
    assert snap.stash_sha


def test_verify_pass_all_steps(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    result = mgr.verify(["python3 -c \"print('ok')\""])
    assert result.passed
    assert result.steps[0].passed


def test_verify_stops_on_first_failure_by_default(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    result = mgr.verify(["python3 -c \"import sys; sys.exit(1)\"", "python3 -c \"print('never runs')\""])
    assert not result.passed
    assert len(result.steps) == 1  # second step never ran


def test_verify_unknown_command_is_reported_not_raised(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    result = mgr.verify(["this_binary_does_not_exist_anywhere_12345"])
    assert not result.passed
    assert result.steps[0].error is not None


def test_rollback_restores_tracked_file_content(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    snap = mgr.create(label="before")

    (repo / "a.py").write_text("print('broken')\n")
    assert (repo / "a.py").read_text() == "print('broken')\n"

    mgr.rollback(snap)
    assert (repo / "a.py").read_text() == "print(1)\n"


def test_rollback_with_no_snapshot_id_uses_latest(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    mgr.create(label="first")
    (repo / "a.py").write_text("print('second state')\n")
    second = mgr.create(label="second")

    (repo / "a.py").write_text("print('broken after second')\n")
    mgr.rollback()  # no snapshot given -> latest == second

    assert (repo / "a.py").read_text() == "print('second state')\n"
    assert mgr.latest().id == second.id


def test_rollback_with_no_snapshots_raises(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    with pytest.raises(SnapshotError, match="No snapshot"):
        mgr.rollback()


def test_list_and_get(repo):
    mgr = SnapshotManager(repo_dir=str(repo), state_dir=str(repo / ".goldenboy"))
    snap = mgr.create(label="one")
    assert [s.id for s in mgr.list()] == [snap.id]
    assert mgr.get(snap.id).label == "one"
    assert mgr.get("does-not-exist") is None

import json
import os

import pytest

from goldenboy.core.checkpoint import CHECKPOINT_SCHEMA_VERSION, CheckpointManager
from goldenboy.core.errors import CheckpointError
from goldenboy.core.priorities import ExecutionUnit, Priority


def test_checkpoint_save_load(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    
    plan = [
        ExecutionUnit("1", "Completed Task", Priority.P0, status="completed"),
        ExecutionUnit("2", "Deferred Task", Priority.P2, status="deferred")
    ]
    
    cm.save("Test Task", plan, "LIMITED")
    
    loaded = cm.load()
    assert loaded is not None
    assert loaded["task_name"] == "Test Task"
    assert loaded["mode"] == "LIMITED"
    
    loaded_plan = loaded["plan"]
    assert len(loaded_plan) == 2
    assert loaded_plan[0].id == "1"
    assert loaded_plan[0].status == "completed"
    assert loaded_plan[1].id == "2"
    assert loaded_plan[1].status == "deferred"
    assert loaded_plan[1].priority == Priority.P2

def test_checkpoint_clear(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)

    cm.save("Test", [], "SAFE")
    assert os.path.exists(cm.checkpoint_file)

    cm.clear()
    assert not os.path.exists(cm.checkpoint_file)


def test_checkpoint_writes_schema_version(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)

    cm.save("Test", [], "SAFE")

    with open(cm.checkpoint_file) as f:
        raw = json.load(f)
    assert raw["version"] == CHECKPOINT_SCHEMA_VERSION


def test_corrupted_json_raises_checkpointerror(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    os.makedirs(checkpoint_dir)
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    with open(cm.checkpoint_file, "w") as f:
        f.write("{not valid json")

    with pytest.raises(CheckpointError, match="corrupted"):
        cm.load()


def test_checkpoint_missing_required_fields_raises_checkpointerror(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    os.makedirs(checkpoint_dir)
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    with open(cm.checkpoint_file, "w") as f:
        json.dump({"units": []}, f)  # no task_name/mode

    with pytest.raises(CheckpointError, match="missing required fields"):
        cm.load()


def test_checkpoint_malformed_unit_raises_checkpointerror(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    os.makedirs(checkpoint_dir)
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    with open(cm.checkpoint_file, "w") as f:
        json.dump(
            {"task_name": "T", "mode": "SAFE", "units": [{"id": "1", "priority": 999}]},
            f,
        )  # priority 999 is not a valid Priority value; description/status missing too

    with pytest.raises(CheckpointError, match="malformed unit data"):
        cm.load()


def test_incompatible_future_version_raises_checkpointerror(tmpdir):
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    os.makedirs(checkpoint_dir)
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    with open(cm.checkpoint_file, "w") as f:
        json.dump(
            {"version": CHECKPOINT_SCHEMA_VERSION + 1, "task_name": "T", "mode": "SAFE", "units": []},
            f,
        )

    with pytest.raises(CheckpointError, match="newer, incompatible version"):
        cm.load()


def test_checkpoint_without_version_field_is_treated_as_version_1(tmpdir):
    """Checkpoints written before the version field existed must still load."""
    checkpoint_dir = os.path.join(tmpdir, ".goldenboy")
    os.makedirs(checkpoint_dir)
    cm = CheckpointManager(checkpoint_dir=checkpoint_dir)
    with open(cm.checkpoint_file, "w") as f:
        json.dump({"task_name": "Old", "mode": "SAFE", "units": []}, f)

    loaded = cm.load()
    assert loaded["task_name"] == "Old"

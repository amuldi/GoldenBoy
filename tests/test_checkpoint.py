import os
from goldenboy.core.priorities import Priority, ExecutionUnit
from goldenboy.core.checkpoint import CheckpointManager

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

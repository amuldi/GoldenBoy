import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_tests():
    # test_budget
    from tests import test_budget
    test_budget.test_budget_usable_percentage()
    test_budget.test_budget_exhausted()
    test_budget.test_budget_is_safe()
    
    # test_executor
    from tests import test_executor
    test_executor.test_executor_safe_mode()
    test_executor.test_executor_limited_mode()
    test_executor.test_executor_critical_mode()
    
    # test_checkpoint
    from tests import test_checkpoint
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_checkpoint.test_checkpoint_save_load(tmpdir)
        test_checkpoint.test_checkpoint_clear(tmpdir)
        
    print("All tests passed successfully.")

if __name__ == "__main__":
    run_tests()

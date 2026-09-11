from goldenboy.core.budget import Budget

def test_budget_usable_percentage():
    b = Budget(remaining_percentage=15.0, safety_margin=3.0)
    assert b.usable_percentage == 12.0
    
def test_budget_exhausted():
    b1 = Budget(remaining_percentage=2.0, safety_margin=3.0)
    assert b1.is_exhausted() is True
    
    b2 = Budget(remaining_percentage=4.0, safety_margin=3.0)
    assert b2.is_exhausted() is False

def test_budget_is_safe():
    b = Budget(remaining_percentage=20.0, safety_margin=5.0)
    # usable is 15.0
    assert b.is_safe(10.0) is True
    assert b.is_safe(16.0) is False

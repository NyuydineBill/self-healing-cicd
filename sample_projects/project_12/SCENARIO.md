# project_12 — Wrong Exception Type

**Break:** `test_divide_by_zero_raises` expects a `RuntimeError`, but `safe_divide` raises `ValueError`.

**Fix:** Change `pytest.raises(RuntimeError)` to `pytest.raises(ValueError)` in the test, or change the raised exception in `app.py` to `RuntimeError`.

**Purpose:** Tests that the repair agent understands exception hierarchies and picks the right fix.

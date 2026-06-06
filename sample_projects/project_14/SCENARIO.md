# project_14 — TypeError: int passed where str expected

**Break:** `test_greet_with_number_name` passes `42` (an int) as `name`. The function does `"Hello, " + name` which raises `TypeError: can only concatenate str (not "int") to str`.

**Fix:** Add `str(name)` conversion in `greet`, or change the test to pass a string.

**Purpose:** Tests that the repair agent handles implicit type coercion bugs and knows whether the fix belongs in the source function or the test.

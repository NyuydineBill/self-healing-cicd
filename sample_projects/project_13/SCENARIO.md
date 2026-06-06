# project_13 — Off-by-one Error

**Break:** `sum_to` uses `range(1, n)` which excludes `n`, returning `n*(n-1)/2` instead of `n*(n+1)/2`.

**Fix:** Change `range(1, n)` to `range(1, n + 1)` in `app.py`.

**Purpose:** Classic off-by-one — tests that the LLM can identify the subtle boundary error in a loop.

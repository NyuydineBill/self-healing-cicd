# project_15 — Retry Recovery Demo

**Purpose:** Demonstrates the framework's multi-attempt retry recovery.

**Bug 1 (stats_helper.py):** `sum_of_squares` adds a spurious `+ 1` offset.
**Bug 2 (math_helper.py):** `square(x)` computes `x³` instead of `x²`.

**Why retry is triggered:**
- Attempt 1: the LLM fixes the visible `+ 1` in `stats_helper.py`. After the
  patch, `sum_of_squares([1,2,3])` returns 36 (1³+2³+3³ = 36) instead of 14.
  Validation still fails — different value, different root cause.
- Attempt 2: armed with both failure messages, the LLM identifies that `square`
  itself is wrong (`x*x*x` should be `x*x`) and patches `math_helper.py`.
  `sum_of_squares` now correctly returns 1+4+9 = 14. Tests pass.

**Golden state:** `square(x) = x*x`, no `+1` in `stats_helper.py`.

# project_11 — Multi-file ImportError

**Break:** `test_multi_file.py` imports `product` from `app`, but `app.py` only defines `multiply`.

**Fix options (either works):**
- Rename `multiply` → `product` in `app.py`, OR
- Change the import in `test_multi_file.py` to `multiply` and update the call.

**Purpose:** Validates multi-file patch repair — the LLM must decide whether to fix the source or the test and patch both consistently.

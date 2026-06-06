# Sample failure scenarios

Each `project_*` folder is a **small, isolated** failure demo for the self-healing pipeline.
By default, all projects are in a **passing (golden)** state so `pytest sample_projects/` is green.

## Projects

| Project | Error category | Golden state | Typical break (script) |
|---------|----------------|--------------|-------------------------|
| `project_1` | AssertionError | Test expects `add(2,2)==4` | Wrong expected value `999` |
| `project_2` | ImportError | Imports `add` from `app` | Imports missing `multiply` |
| `project_3` | SyntaxError | Valid `app.py` | Invalid syntax in `app.py` |
| `project_4` | Logic bug | `add` returns sum | `add` returns difference |
| `project_5` | ModuleNotFoundError | Valid imports | Imports fake module |
| `project_6` | AttributeError | Calls `add()` | Calls `add_numbers()` |
| `project_7` | NameError | Uses defined name | Uses undefined variable in `app` |
| `project_8` | IndexError | Safe index access | Index past end of list |
| `project_9` | TypeError | Numeric add | Concatenates or wrong types |
| `project_10` | ZeroDivisionError | Safe divide | Divides by zero |
| `project_11` | Multi-file ImportError | `test` imports correct name from `app` | `app.py` exports `multiply`; test imports `product` — root cause spans two files |
| `project_12` | Wrong exception type | Test expects `ValueError` | `app.py` raises `RuntimeError` — mismatch between raised and expected exception |
| `project_13` | Off-by-one | `sum_to(5) == 15` | `range(1, n)` excludes `n`; should be `range(1, n+1)` |
| `project_14` | Type coercion (TypeError) | `greet("Alice", 1)` works | Test passes `42` (int) as name; `"Hello, " + name` raises TypeError |

## Trigger a failure for CI / self-heal

```bash
# Break one project (default: project_1)
./scripts/break-sample.sh 1

# Reset all samples to passing
./scripts/reset-samples.sh

git add sample_projects/
git commit -m "test: intentional CI failure in project_N"
git push origin main
```

Watch: **Test Pipeline** (fail) → **Self-Heal on Failure**.

## Notes

- `ALLOWED_PATH_PREFIXES=auto` (default) — the framework auto-discovers `sample_projects/` without any config.
- Validation replays the exact failing CI command when available; falls back to scoped `pytest` per project.
- Projects 11–14 are designed for the **multi-file repair** path — root cause may span `app.py` and the test file.
- Break one project at a time for clearest demos.

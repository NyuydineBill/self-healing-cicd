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

- Only paths under `ALLOWED_PATH_PREFIXES` (includes `sample_projects/`) can be patched.
- Validation runs **scoped pytest** per project directory.
- Break one project at a time for clearest demos.

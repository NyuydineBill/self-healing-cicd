# Improvements Applied

This document records every change made to bring the project up to production-grade standards, what problem each change solves, and where the affected files live.

---

## 1. Python Packaging — `pyproject.toml`

**File:** [pyproject.toml](pyproject.toml)

Added a `pyproject.toml` with:
- Project metadata (name, version `0.1.0`, description, license, author, Python requirement `>=3.12`).
- `[project.dependencies]` mirroring `requirements.txt` so the package is pip-installable via `pip install .`.
- `[project.optional-dependencies] dev` listing `pytest-cov`, `ruff`, `mypy`, `bandit`, `pip-audit`, `pre-commit`, and `types-requests` — installable with `pip install -e ".[dev]"`.
- `[project.scripts]` exposing `self-heal = "main:main"` so `self-heal` is a CLI command after installation.
- `[tool.pytest.ini_options]`, `[tool.coverage.*]`, `[tool.mypy]`, `[tool.ruff.*]`, and `[tool.bandit]` sections consolidating all tool config in one file.

**Why it matters:** Without this the project can only be used by cloning the repo and running `python main.py`. With it, `pip install self-healing-cicd` works and downstream projects can depend on it.

---

## 2. Reproducible Dependency Lockfile — `requirements.lock`

**File:** [requirements.lock](requirements.lock)

Generated from `pip freeze` of the active venv. Contains every transitive dependency at an exact version (e.g. `openai==2.36.0`, `httpx==0.28.1`).

**Why it matters:** `requirements.txt` specifies minimums (`openai>=1.0.0`) but not exact versions, so two installs a week apart can produce different environments. The lockfile pins everything so CI and production always use the same bytes.

---

## 3. Test Coverage Measurement

**Files:** [pytest.ini](pytest.ini), [pyproject.toml](pyproject.toml), [.github/workflows/test.yml](.github/workflows/test.yml)

- Added `--cov=. --cov-report=term-missing --cov-report=xml --cov-omit=venv/*,tests/*,sample_projects/*` to `pytest.ini addopts`.
- `pyproject.toml` sets `fail_under = 40` as a starting gate.
- CI installs `pytest-cov` and uploads `coverage.xml` as a workflow artifact.

**Why it matters:** With no coverage instrumentation there was no way to measure or trend test quality. Now every CI run reports per-module coverage and fails if it drops below the configured threshold.

---

## 4. Linting & Formatting — Ruff

**Files:** [pyproject.toml](pyproject.toml) (`[tool.ruff]` section)

Configured `ruff` with:
- `line-length = 100`, `target-version = "py312"`.
- Selected rule sets: `E/F/W` (pycodestyle/pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear), `C4` (flake8-comprehensions), `SIM` (flake8-simplify).
- Known-first-party packages listed so import ordering is correct.

**Why it matters:** No linter was configured previously. Ruff enforces consistent style and catches real bugs (unused imports, mutable default args, etc.) in milliseconds.

---

## 5. Type Checking — Mypy

**Files:** [pyproject.toml](pyproject.toml) (`[tool.mypy]` section)

Configured `mypy` with `disallow_untyped_defs = true` and `ignore_missing_imports = true`. Excludes `venv/`, `sample_projects/`, and `scripts/`.

**Why it matters:** The codebase has type hints throughout but they were never validated. Mypy turns them into actual checks that catch type errors before runtime.

---

## 6. Pre-commit Hooks — `.pre-commit-config.yaml`

**File:** [.pre-commit-config.yaml](.pre-commit-config.yaml)

Hooks configured:
- `ruff` — lint with auto-fix.
- `ruff-format` — enforce formatting.
- `mypy` — type check on changed files.
- `bandit` — SAST scan.
- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-merge-conflict`, `detect-private-key` from pre-commit-hooks.

Install with `pre-commit install` after cloning.

**Why it matters:** Catches issues locally before they reach CI, reducing round-trip time on failures.

---

## 7. CI Pipeline Upgrade — `.github/workflows/test.yml`

**File:** [.github/workflows/test.yml](.github/workflows/test.yml)

Split into three parallel jobs:

| Job | Steps |
|-----|-------|
| **lint** | `ruff check`, `ruff format --check`, `mypy` |
| **security** | `bandit` (SAST), `pip-audit` (CVE scan); both reports uploaded as artifacts |
| **test** | `pytest` with `pytest-cov`; `coverage.xml` uploaded as artifact |

**Why it matters:** Previously CI only ran `pytest`. Now every PR is automatically checked for style, type errors, known vulnerabilities, and test coverage.

---

## 8. Dependabot — `.github/dependabot.yml`

**File:** [.github/dependabot.yml](.github/dependabot.yml)

Configured weekly scans for:
- `pip` dependencies (grouped dev vs. runtime).
- `github-actions` — keeps `actions/checkout`, `actions/setup-python`, etc. up to date.

**Why it matters:** Without Dependabot, dependency updates require manual effort. CVEs in transitive dependencies go undetected until someone checks.

---

## 9. Audit Logging — `utils/audit_log.py`

**File:** [utils/audit_log.py](utils/audit_log.py)

New module providing four functions:

| Function | When called |
|----------|-------------|
| `record_patch_applied` | After a patch is written to disk |
| `record_patch_rejected` | When validation fails or user denies approval |
| `record_pr_opened` | When a repair PR is opened on GitHub |
| `record_run_outcome` | At the end of each repair run |

Each call appends a newline-delimited JSON record to `results/audit.log` with `timestamp`, `event`, `run_id`, `target_file`, `actor`, and event-specific fields. Write failures are caught and logged as warnings so they never crash the repair flow.

**Why it matters:** Previously there was no persistent, structured record of what the bot changed and why. The audit log provides an immutable trail for post-mortems and compliance.

---

## 10. Prompt Injection Sanitization — `utils/prompts.py`

**File:** [utils/prompts.py](utils/prompts.py)

Added `_sanitize()` applied to all string template variables before LLM interpolation:
- Strips ASCII control characters (`\x00–\x1f`, `\x7f`) that could corrupt the prompt.
- Regex-matches known injection phrases (`ignore previous instructions`, `new system prompt`, `<|im_start|>`, etc.) and replaces them with `[REDACTED]`, logging a warning.

**Why it matters:** LLM prompts are built from failure logs sourced from GitHub Actions. A malicious test file or log line could craft content designed to redirect the LLM. Sanitization closes this vector.

---

## 11. Correlation IDs in Logging — `utils/logging.py`

**File:** [utils/logging.py](utils/logging.py)

- Added a `contextvars.ContextVar[str]` named `_run_id_var` to carry the current run ID through all log calls without threading it through every function signature.
- Exported `set_run_id(run_id)` and `get_run_id()`.
- Updated the log format to `%(asctime)s | %(levelname)-8s | %(run_id)s | %(name)s | %(message)s`.
- Replaced the single `SecretsRedactionFilter` class with `_ContextFilter` that does both secret masking and run_id injection.

**Why it matters:** With multiple repair runs interleaved in logs it was impossible to trace a single run end-to-end. Every log line now carries the run ID.

---

## 12. Log Rotation — `utils/logging.py`

**File:** [utils/logging.py](utils/logging.py)

Added a `RotatingFileHandler` writing to `logs/self_healing.log`:
- Max file size: 5 MB.
- Keeps 5 backups (`self_healing.log.1` … `.5`).
- Falls back gracefully if the log directory is not writable (e.g. read-only CI environments).

**Why it matters:** Previously logs written to `logs/` would grow without bound across runs.

---

## 13. LLM Cost Tracking — `utils/llm_client.py`

**File:** [utils/llm_client.py](utils/llm_client.py)

After every successful OpenAI call, `_log_usage()` logs:
- `prompt_tokens`, `completion_tokens`, `total_tokens`.
- `est_cost_usd` — calculated from a built-in rate table for common GPT-4o and GPT-3.5 models.

**Why it matters:** The retry loop can multiply API calls. Without cost visibility a misconfigured run can accumulate unexpected spend silently.

---

## 14. Docker Build Hygiene — `.dockerignore`

**File:** [.dockerignore](.dockerignore)

Excludes from the Docker build context: `venv/`, `__pycache__/`, `.env`, `.git/`, `logs/`, `results/*.json`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `coverage.xml`, and `*.zip`.

**Why it matters:** Without this, `COPY . .` in the Dockerfile sent the entire repo (including venv and cached logs) into the image, bloating build times and potentially leaking secrets from `.env` if the image were ever pushed.

---

## 15. Line Ending Consistency — `.gitattributes`

**File:** [.gitattributes](.gitattributes)

Sets `* text=auto eol=lf` globally and explicitly marks Python, YAML, TOML, Markdown, JSON, and shell files as `eol=lf`. Binary files (zip, pyc, images) are marked `binary`.

**Why it matters:** Mixed CRLF/LF line endings in shell scripts and YAML can cause `\r: command not found` errors on Linux runners.

---

## 16. Updated `.gitignore`

**File:** [.gitignore](.gitignore)

Added entries for:
- `.coverage`, `coverage.xml`, `htmlcov/` — pytest-cov output.
- `.mypy_cache/`, `.ruff_cache/` — linter caches.
- `*.egg-info/`, `dist/`, `build/` — packaging artifacts.
- `results/audit.log` — audit log (runtime-generated, not version-controlled).
- `.DS_Store` — macOS metadata.

---

## 17. Documentation

### [CONTRIBUTING.md](CONTRIBUTING.md)
Developer setup, test commands, lint commands, guidelines for adding new language parsers and agents, PR etiquette, and commit message style.

### [SECURITY.md](SECURITY.md)
Vulnerability disclosure contact, supported versions table, summary of security design decisions (secrets masking, path allowlist, approval gates, prompt sanitization, audit trail), and known limitations.

### [LICENSE](LICENSE)
MIT license — was referenced in `README.md` but the file did not exist.

### [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
Step-by-step resolution for the most common errors: missing tokens, Docker not running, 403 on PR creation, no failed runs found, LLM timeout, ruff/mypy CI failures, and web approval UI networking. Includes a log locations reference table.

---

## 18. Typing Modernisation — Codebase-wide

**Files:** all modules under `agents/`, `config/`, `parsers/`, `utils/`, `tests/`

Applied ruff `UP` (pyupgrade) and `F` (pyflakes) auto-fixes across the entire codebase:
- Replaced deprecated `typing.List`, `Dict`, `Tuple`, `Optional`, `Type`, `Set` with Python 3.10+ builtins (`list`, `dict`, `tuple`, `X | None`, `type`, `set`).
- Replaced `Optional[X]` annotations with `X | None` union syntax.
- Replaced `class ErrorCategory(str, Enum)` with `class ErrorCategory(StrEnum)`.
- Removed all unused imports surfaced by `F401`.
- Used `datetime.UTC` alias instead of `timezone.utc` (`UP017`).
- Removed unnecessary `open()` mode `"r"` arguments (`UP015`).
- Collapsed nested `if` statements into compound conditions (`SIM102`).
- Excluded `tests/` from mypy in both `pyproject.toml` and `.pre-commit-config.yaml` — test functions do not require return type annotations.

**Why it matters:** The codebase had type hints written in pre-3.10 style that triggered 104 ruff violations. All are now clean and the pre-commit hooks enforce the modern style on every future commit.

---

## 19. GitHub Action — `action.yml`

**File:** [action.yml](action.yml)

Added a GitHub composite action so any repository can consume the self-healer without cloning or copying workflow files:

```yaml
- uses: NyuydineBill/self-healing-cicd@v0.1.0
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    openai-api-key: ${{ secrets.OPENAI_API_KEY }}
```

**Inputs exposed:**

| Input | Default | Purpose |
|-------|---------|---------|
| `github-token` | — | Required. Token with `repo` + `actions:read` scope |
| `openai-api-key` | — | Required. OpenAI key for LLM calls |
| `github-owner` | repo owner | GitHub owner of the target repo |
| `github-repo` | repo name | Repository to monitor |
| `openai-model` | `gpt-4o-mini` | LLM model |
| `max-retry-attempts` | `3` | Patch-and-validate retries |
| `dry-run` | `false` | Skip file writes and Docker |
| `git-enabled` | `true` | Commit repairs and open PRs |
| `git-create-pr` | `true` | Open a PR after repair |
| `git-base-branch` | `main` | PR target branch |
| `allowed-path-prefixes` | `auto` | Files the patcher may touch (auto = scan repo) |
| `max-failed-runs` | `5` | Max runs to process |

CI-safe defaults are set automatically: `REQUIRE_APPROVAL=false`, `AUTO_APPROVE_PATCHES=true`, `WEB_APPROVAL_ENABLED=false`.

The action installs the package from its own checked-out source (`pip install ${{ github.action_path }}`), so pinning `@v0.1.0` guarantees reproducibility.

**Why it matters:** Without this, users had to copy `self-heal.yml` into their repo manually. The action reduces adoption to two lines in any workflow.

---

## 20. Automated Release Pipeline — `.github/workflows/publish.yml`

**File:** [.github/workflows/publish.yml](.github/workflows/publish.yml)

Added a release workflow that triggers on `v*` tags and runs three sequential jobs:

| Job | What it does |
|-----|-------------|
| `test` | Runs the full `pytest` suite — publish is blocked if tests fail |
| `publish-pypi` | Builds wheel + sdist with `python -m build`; publishes to PyPI via OIDC trusted publisher (no API token stored in secrets) |
| `github-release` | Creates a GitHub Release with auto-generated notes and the `.whl` / `.tar.gz` dist files attached |

**Publishing a new version:**
```bash
git tag v0.x.x
git push origin v0.x.x
```

**Why it matters:** Previously there was no release automation. Now the entire publish pipeline — test → build → PyPI → GitHub Release — runs automatically on every tag in under 2 minutes. The OIDC trusted publisher means no long-lived PyPI credentials are stored anywhere.

**First release:** `v0.1.0` was published successfully on 2026-06-05. Package available at [pypi.org/project/self-healing-cicd](https://pypi.org/project/self-healing-cicd).

---

---

## 21. CI Command Replay Validation — v0.1.9

**Files:** [agents/analysis_agent.py](agents/analysis_agent.py), [agents/validation_agent.py](agents/validation_agent.py), [config/settings.py](config/settings.py)

Instead of always building Docker and running `pytest`, the validator now:

1. Extracts the failing CI command from `##[group]Run`, `[command]`, or `set -x` trace in the GitHub Actions log (`extract_failing_command()`).
2. Safety-checks the binary against an allowlist and an unsafe-pattern block-list (`_is_replayable()`).
3. Re-runs the exact command locally to validate the patch (`_validate_by_replay()`).
4. Falls back to Docker + `pytest` only when no replayable command is found.

New setting: `VALIDATION_TIMEOUT` (default 120 s) — configurable subprocess timeout for the replay.

**Why it matters:** Validation previously required Docker and was tied to `pytest`. Command replay works for any test runner or linter (ruff, mypy, npm test, go test, cargo test) without Docker. Teams that don't use Docker at all can now use the framework.

---

## 22. Auto-Discovery of Source Directories — v0.1.9

**Files:** [utils/policy.py](utils/policy.py), [utils/discovery.py](utils/discovery.py), [action.yml](action.yml)

`ALLOWED_PATH_PREFIXES` now defaults to **`auto`**. When set to `auto` (or left empty), `auto_discover_prefixes()` scans the repo for `.py/.js/.ts/.go/.rs` files and returns the unique top-level directories as the allowlist — no manual configuration required.

`discover_all_test_targets()` falls back to `discover_source_files()` when no test files are found, so projects without a `tests/` folder are still repairable.

The `action.yml` `allowed-path-prefixes` input default was updated from a hardcoded list to `auto`.

**Why it matters:** New users had to know the exact folder layout before setting `ALLOWED_PATH_PREFIXES`. Auto-discovery removes that friction entirely — the framework figures it out.

---

## 23. Multi-File Repair — v0.1.10

**Files:** [agents/patch_agent.py](agents/patch_agent.py), [config/prompts/multi_patch.txt](config/prompts/multi_patch.txt), [orchestrator/workflow.py](orchestrator/workflow.py), [utils/file_backup.py](utils/file_backup.py), [utils/git_repair.py](utils/git_repair.py)

The patcher now repairs **all files involved in a failure** in one atomic LLM call instead of only the single primary file.

Key additions:

| Component | Purpose |
|-----------|---------|
| `FilePatch` dataclass | Holds `file_path` + `new_content` for one file |
| `_collect_context_files()` | Reads primary files and walks their local imports to build full context |
| `generate_multi_patch()` | Sends combined context to LLM; returns `list[FilePatch]` |
| `_parse_multi_patch()` | Strips markdown fences, validates JSON array, filters to allowed paths |
| `apply_multi_patch()` | Applies all patches atomically via `NamedTemporaryFile` + `Path.replace()` |
| `config/prompts/multi_patch.txt` | Prompt asking LLM for `[{"file": "...", "content": "..."}]` |

`WorkflowResult.target_files: list[str]` tracks all repaired files. The git commit and PR body list every file changed.

Multi-file backup/restore (`backup_originals`, `restore_originals`, `clear_run_backups_list`) added to `utils/file_backup.py`.

**Why it matters:** ImportErrors, cross-module type bugs, and split source/test fixes all require changing more than one file. The single-file patcher would patch the test but leave the broken source. Multi-file repair gives the LLM the full picture.

---

## 24. Sample Projects 11–14 — v0.1.11

**Files:** [sample_projects/project_11/](sample_projects/project_11/), [project_12/](sample_projects/project_12/), [project_13/](sample_projects/project_13/), [project_14/](sample_projects/project_14/)

Four new intentionally-failing demo scenarios added to exercise edge cases the original ten projects did not cover:

| Project | Failure | Exercises |
|---------|---------|-----------|
| `project_11` | Multi-file ImportError — `app.py` exports `multiply`, test imports `product` | Multi-file repair path |
| `project_12` | Wrong exception type — `app.py` raises `RuntimeError`, test expects `ValueError` | Exception mismatch diagnosis |
| `project_13` | Off-by-one — `range(1, n)` excludes `n`; `sum_to(5)` returns 10 instead of 15 | Subtle boundary bug |
| `project_14` | Type coercion TypeError — `greet` uses string concat, test passes `42` as name | Source vs. test fix decision |

---

## 25. Reliability Hardening — v0.1.11

**Files:** multiple agents and utilities

Small targeted fixes that prevent silent failures in production:

| Module | Fix | Risk mitigated |
|--------|-----|---------------|
| `agents/monitoring_agent.py` | `.get("workflow_runs", [])` | `KeyError` crash on unexpected GitHub API shape |
| `agents/reasoning_agent.py` | Warning log when LLM returns empty string | Silent empty-diagnosis producing nonsense patches |
| `agents/patch_agent.py` | Atomic write: `NamedTemporaryFile` + `Path.replace()` | Partial file corruption on interrupted write |
| `agents/analysis_agent.py` | Filter paths through `Path(f).is_file()` | Passing non-existent paths to LLM context/repair |
| `agents/validation_agent.py` | Uses `self.validation_timeout` from settings | Hardcoded 120 s could not be tuned for slow runners |
| `utils/approval.py` | `try/except EOFError` around `input()` | CI crash when stdin is closed |
| `parsers/python_parser.py` | Broader fallback `FILE_PATTERN`; ordered-dict dedup | Missed file references; duplicate entries in context |
| `parsers/__init__.py` | INFO log on fallback parser selection | Silent parser selection made debugging harder |
| `config/settings.py` | `validation_timeout` field (`VALIDATION_TIMEOUT` env) | No way to tune replay timeout without code change |

---

## Summary Table

| # | What | File(s) | Category |
|---|------|---------|----------|
| 1 | Modern Python packaging | `pyproject.toml` | Packaging |
| 2 | Reproducible lockfile | `requirements.lock` | Packaging |
| 3 | Coverage measurement | `pytest.ini`, `pyproject.toml`, CI | Testing |
| 4 | Ruff linting | `pyproject.toml` | Code quality |
| 5 | Mypy type checking | `pyproject.toml` | Code quality |
| 6 | Pre-commit hooks | `.pre-commit-config.yaml` | Code quality |
| 7 | CI pipeline (lint + SAST + test) | `.github/workflows/test.yml` | CI/CD |
| 8 | Dependabot | `.github/dependabot.yml` | Security |
| 9 | Audit logging | `utils/audit_log.py` | Security |
| 10 | Prompt injection sanitization | `utils/prompts.py` | Security |
| 11 | Correlation run IDs in logs | `utils/logging.py` | Observability |
| 12 | Log rotation | `utils/logging.py` | Observability |
| 13 | LLM cost tracking | `utils/llm_client.py` | Observability |
| 14 | Docker build hygiene | `.dockerignore` | Docker |
| 15 | Line ending consistency | `.gitattributes` | Git hygiene |
| 16 | Extended .gitignore | `.gitignore` | Git hygiene |
| 17 | CONTRIBUTING, SECURITY, LICENSE, TROUBLESHOOTING | `*.md`, `LICENSE` | Documentation |
| 18 | Typing modernisation (104 ruff UP/F fixes) | all modules | Code quality |
| 19 | GitHub Action | `action.yml` | Distribution |
| 20 | Automated PyPI + GitHub Release pipeline | `.github/workflows/publish.yml` | Distribution |
| 21 | CI command replay validation | `agents/analysis_agent.py`, `agents/validation_agent.py` | Validation |
| 22 | Auto-discovery of source directories | `utils/policy.py`, `utils/discovery.py` | Usability |
| 23 | Multi-file repair | `agents/patch_agent.py`, `config/prompts/multi_patch.txt` | Core capability |
| 24 | Sample projects 11–14 (edge case demos) | `sample_projects/project_11-14/` | Testing |
| 25 | Reliability hardening (9 targeted fixes) | agents, parsers, utils | Reliability |

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

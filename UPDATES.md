# Self-Healing CI/CD — Architecture Upgrade Changelog

This document records every update made to introduce a production-style orchestration layer while preserving compatibility with the existing agent-based architecture.

---

## Summary

The framework was refactored from a linear script in `main.py` into a modular pipeline with:

- **`orchestrator/`** — workflow coordination and retry management
- **`utils/`** — logging, error categorization, prompts, failure memory, log extraction, Docker cleanup
- **`config/`** — centralized settings and externalized prompt templates
- **`results/`** — structured JSON persistence for metrics and run outcomes

All five original agents (`MonitoringAgent`, `AnalysisAgent`, `ReasoningAgent`, `PatchAgent`, `ValidationAgent`) remain the execution units; `main.py` now delegates to `WorkflowOrchestrator`.

---

## Update: Git commit fix (latest)

- **`utils/git_repair.py`**: use `git.Actor(name, email)` for commits (fixes `AttributeError: 'str' object has no attribute 'name'` in GitHub Actions).
- Repair can succeed in validation but no longer crashes on commit; git errors are logged and returned in `git_info`.

---

## Update: CI pre-flight fix

- **Offline log cache** no longer fails pre-flight when empty unless `OFFLINE_MODE=true` (fixes GitHub Actions check on fresh runners).
- **self-heal.yml** check step now sets `GIT_ENABLED=true` so git repository is validated before heal.

---

## Update: Full product release

Production-grade features for real deployment beyond thesis demo.

| Feature | Module | Description |
|---------|--------|-------------|
| Pre-flight CLI | `config/check.py`, `python main.py check` | Validates env, Docker, git, prompts, writable dirs |
| Patch approval | `utils/approval.py` | Unified diff + `[y/N]` before apply; `AUTO_APPROVE_PATCHES` for CI |
| Path policy | `utils/policy.py` | `ALLOWED_PATH_PREFIXES` allowlist |
| Offline mode | `utils/offline_logs.py`, `OFFLINE_MODE=true` | Repair from `logs/extracted/` without GitHub API |
| API resilience | `utils/http_retry.py` | Retry/backoff on 403, 429, 5xx |
| Loop guard | `MonitoringAgent` | Skips `EXCLUDED_WORKFLOW_NAMES` (default: self-heal workflows) |
| CI hardening | `self-heal.yml` | Pre-flight step + `AUTO_APPROVE_PATCHES=true` |

### New environment variables

`REQUIRE_APPROVAL`, `AUTO_APPROVE_PATCHES`, `APPROVAL_DIFF_MAX_LINES`, `ALLOWED_PATH_PREFIXES`, `OFFLINE_MODE`, `GITHUB_API_MAX_RETRIES`, `EXCLUDED_WORKFLOW_NAMES`

### New tests (34 total)

`test_policy.py`, `test_approval.py`, `test_offline_logs.py`

### Product usage summary

1. `python main.py check` → 2. local with approval OR CI with auto-approve → 3. review PR → merge

---

## Update: README documentation

- **Mermaid architecture diagram** in `README.md` (entry → orchestrator → agents → utils)
- **How people use this framework** — three modes: thesis/dry-run, local operator, CI-attached self-heal
- **Limitations** — one-page section (scope, ops, security, CI, adoption gaps)
- **Completion checklist** for thesis vs live GitHub demo

---

## Update: Production Polish

Implements **README**, **Git integration (branch/commit/PR)**, **secrets masking**, and **GitHub Actions self-heal workflow**.

### 1. README (`README.md`)

Quick start, architecture diagram, env table, git/CI notes, output paths. Points to `UPDATES.md` for full history.

### 2. Git integration (`utils/git_repair.py`)

| Step | Behavior |
|------|----------|
| Branch | `self-heal/run-{id}-{timestamp}` from current HEAD (keeps validated patches) |
| Commit | One commit per successful repair on that branch |
| Push | HTTPS push using `GITHUB_TOKEN` |
| PR | GitHub REST API (`GIT_CREATE_PR=true`) |

**Settings:** `GIT_ENABLED`, `GIT_CREATE_PR`, `GIT_BRANCH_PREFIX`, `GIT_BASE_BRANCH`, `GIT_PUSH_REMOTE`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`

Orchestrator calls `commit_repair` on success and `finalize_run` after each workflow run. `WorkflowResult.git_info` stores branch/PR URL.

### 3. Secrets masking (`utils/secrets.py`)

- `SecretsRedactionFilter` on all log handlers
- Masks `ghp_*`, `sk-*`, `Bearer *`, and registered env secrets
- `safe_patch_summary()` — logs patch size only (no body at INFO)
- `truncate_for_log()` — safe API error snippets
- Diagnosis/patch content moved to DEBUG with length-only INFO lines

### 4. GitHub Actions hook (`.github/workflows/self-heal.yml`)

Triggers when **Test Pipeline** completes with `failure`. Runs `python main.py` with:

- `contents: write`, `pull-requests: write`
- `GIT_ENABLED=true`, secrets for `GITHUB_TOKEN` and `OPENAI_API_KEY`

Skips PR-triggered workflow runs to avoid loops.

### Files added/modified

| File | Change |
|------|--------|
| `README.md` | **NEW** |
| `utils/git_repair.py` | **NEW** |
| `utils/secrets.py` | **NEW** |
| `utils/logging.py` | Redaction filter |
| `orchestrator/workflow.py` | Git hooks, safe logging |
| `.github/workflows/self-heal.yml` | **NEW** |
| `tests/test_secrets.py` | **NEW** |
| `tests/test_git_repair.py` | **NEW** |
| `.env.example` | Git + log settings |

---

## Update: Medium-Priority Reliability

Implements the four medium-priority items: **unit tests**, **multi-failure processing**, **scoped Docker validation**, and **LLM timeouts/retries**.

### 1. Unit tests (`tests/`)

22 tests covering core utilities and orchestrator logic (mocked agents, no live API/Docker):

| Module | Tests |
|--------|-------|
| `test_errors.py` | Error categorization |
| `test_prompts.py` | Template loading and variable substitution |
| `test_file_backup.py` | Backup, restore, cleanup |
| `test_validation_scope.py` | Scoped pytest path resolution |
| `test_config_validation.py` | Startup validation rules |
| `test_llm_client.py` | Retry and backoff |
| `test_orchestrator.py` | Multi-failure, deduplication, dry-run |

Run: `pytest tests/` (CI updated to use `pytest tests/ -v`).

### 2. Multi-failure processing

- Processes up to `MAX_FAILED_RUNS` failed workflow runs (default: 5)
- Per run, handles up to `MAX_FAILURES_PER_RUN` distinct targets (default: 10)
- Deduplicates `(run_id, target_file)` so the same file is not repaired twice from multiple logs
- `STOP_ON_FIRST_SUCCESS=true` (default): stops after first successful repair across runs
- Returns `BatchWorkflowResult` with a list of `WorkflowResult` entries

### 3. Scoped Docker validation

- `ValidationAgent.validate_patch(target_file=...)` runs `pytest sample_projects/project_N` instead of the full repo
- `utils/validation_scope.py` — `resolve_validation_scope()` derives project path from target file
- `VALIDATE_FULL_REPO=true` restores full-repo `pytest` behavior
- Validation results include `scope` field; retry context includes scope

### 4. LLM timeouts and retries

- `utils/llm_client.py` — `chat_completion_with_retry()` with exponential backoff
- Used by `ReasoningAgent` and `PatchAgent`
- Settings: `OPENAI_TIMEOUT` (default 60s), `OPENAI_MAX_RETRIES` (default 3)
- Docker build/run also use 300s subprocess timeouts

### New settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FAILED_RUNS` | `5` | Max failed GitHub runs to process per execution |
| `MAX_FAILURES_PER_RUN` | `10` | Max distinct file failures per run |
| `STOP_ON_FIRST_SUCCESS` | `true` | Stop after first successful repair |
| `OPENAI_TIMEOUT` | `60` | LLM request timeout (seconds) |
| `OPENAI_MAX_RETRIES` | `3` | LLM retry attempts |
| `VALIDATE_FULL_REPO` | `false` | Run full `pytest` instead of scoped project |

### API change

`WorkflowOrchestrator.run()` now returns **`BatchWorkflowResult`** (not a single `WorkflowResult`). `main.py` logs each sub-result.

### Files added

| Path |
|------|
| `tests/` (7 test modules + `conftest.py`) |
| `pytest.ini` |
| `utils/llm_client.py` |
| `utils/validation_scope.py` |

### Files modified

| File | Change |
|------|--------|
| `orchestrator/workflow.py` | Multi-run/multi-failure loop, `BatchWorkflowResult` |
| `orchestrator/__init__.py` | Export `BatchWorkflowResult` |
| `agents/validation_agent.py` | Scoped pytest, timeouts, `target_file` param |
| `agents/reasoning_agent.py` | LLM retry wrapper |
| `agents/patch_agent.py` | LLM retry wrapper |
| `config/settings.py` | New orchestration and OpenAI settings |
| `config/validation.py` | Validate new numeric settings |
| `main.py` | Handle `BatchWorkflowResult` |
| `.env.example` | New variables |
| `.github/workflows/test.yml` | `pytest tests/` |

---

## Update: Production Safety Features

Adds the high-priority hardening items: **file backup/rollback**, **startup config validation**, **`.env.example`**, and **dry-run mode**.

### What was added

| Feature | Location | Behavior |
|---------|----------|----------|
| File backup & rollback | `utils/file_backup.py` | Copies target file to `results/backups/{run_id}/` before patching; restores on failed validation and after exhausted retries; clears backups on success |
| Config validation | `config/validation.py` | `validate_configuration()` runs before orchestration; raises `ConfigurationError` with a bullet list of missing items |
| Environment template | `.env.example` | Copy-paste template for all supported variables |
| Dry-run mode | `config/settings.py`, `orchestrator/workflow.py` | `DRY_RUN=true` runs diagnosis + patch generation only; no file writes, no Docker |

### New / updated settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DRY_RUN` | `false` | Skip `apply_patch` and Docker validation |
| `BACKUP_BEFORE_PATCH` | `true` | Enable backup/restore around patches |

### Config validation rules

**Live mode** (`DRY_RUN=false`):

- Requires: `OPENAI_API_KEY`, `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`
- Checks: Docker available (`docker info`), prompt templates exist, `MAX_RETRY_ATTEMPTS >= 1`

**Dry-run mode** (`DRY_RUN=true`):

- Requires: `OPENAI_API_KEY` only
- Skips: GitHub and Docker checks (GitHub is still used if the full pipeline runs)

### Backup layout

```
results/backups/{run_id}/
  sample_projects__project_1__test_unit_failure.py.original.bak
  sample_projects__project_1__test_unit_failure.py.attempt1.bak
```

### Orchestrator changes

- New status: `dry_run_complete` — first attempt finished without modifying files
- `_persist_result` includes `dry_run` flag in JSON output
- On each failed attempt: `restore_original()` before next retry
- After all retries fail: final `restore_original()`
- On success: `clear_run_backups()` removes `.bak` files for that run

### `main.py` changes

- Calls `validate_configuration()` before starting orchestrator
- Exit code `2` on configuration errors
- Exit code `0` on `dry_run_complete` or `no_failures`

### Quick start (safe first run)

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY at minimum

# Safe trial: no file changes, no Docker
DRY_RUN=true python main.py

# Full repair (requires GitHub + Docker)
python main.py
```

### Files touched in this update

| File | Change |
|------|--------|
| `config/settings.py` | Added `dry_run`, `backup_before_patch` |
| `config/__init__.py` | Export `ConfigurationError`, `validate_configuration` |
| `config/validation.py` | **NEW** — startup validation |
| `utils/file_backup.py` | **NEW** — backup manager |
| `utils/__init__.py` | Export `FileBackupManager` |
| `orchestrator/workflow.py` | Backup, restore, dry-run branches |
| `main.py` | Config validation + exit codes |
| `.env.example` | **NEW** — environment template |
| `.gitignore` | Ignore `results/backups/` |

---

## New Directory Structure

```
self-healing-cicd/
├── orchestrator/
│   ├── __init__.py
│   └── workflow.py          # WorkflowOrchestrator, WorkflowResult, RepairAttempt
├── utils/
│   ├── __init__.py
│   ├── logging.py           # Structured logging setup
│   ├── errors.py            # ErrorCategory enum + categorize_failure()
│   ├── prompts.py           # load_prompt() from template files
│   ├── failure_memory.py    # JSON persistent repair history
│   ├── discovery.py         # discover_sample_tests() (moved from main.py)
│   ├── log_extractor.py       # ZIP save/extract + log file iteration
│   ├── docker_utils.py      # Container/image cleanup after validation
│   ├── file_backup.py       # Backup/restore before and after patches
│   ├── llm_client.py        # OpenAI retry + timeout wrapper
│   ├── validation_scope.py  # Scoped pytest path from target file
│   └── results_store.py     # Per-run and metrics JSON persistence
├── config/
│   ├── __init__.py
│   ├── settings.py          # Settings dataclass + get_settings()
│   ├── validation.py        # Startup config validation
│   └── prompts/
│       ├── diagnosis.txt    # LLM diagnosis template
│       └── patch.txt        # LLM patch generation template
├── results/
│   └── .gitkeep             # Runtime JSON written here (gitignored)
├── agents/
│   └── __init__.py          # NEW — package exports
└── UPDATES.md               # This file
```

---

## 1. Orchestrator Module (`orchestrator/`)

### `orchestrator/workflow.py`

| Component | Purpose |
|-----------|---------|
| `WorkflowOrchestrator` | Coordinates all agents end-to-end |
| `WorkflowResult` | Structured outcome (status, attempts, repair_success) |
| `RepairAttempt` | Per-attempt record (diagnosis, patch, validation) |

**Behavior:**

1. Fetches failed GitHub Actions runs via `MonitoringAgent`
2. Downloads and extracts logs via `utils/log_extractor.py`
3. Parses errors and resolves target file via `AnalysisAgent` + `discover_sample_tests()`
4. Categorizes failure type via `utils/errors.categorize_failure()`
5. Runs repair loop up to `MAX_RETRY_ATTEMPTS` (default: 3)
6. On each attempt: diagnose → generate patch (with diagnosis) → apply → validate
7. Enriches failure context with validation output between retries
8. Records each attempt in `FailureMemory` and persists results via `ResultsStore`
9. Cleans up Docker containers/images after validation

**Batch statuses:** `no_failures`, `completed`, `no_errors_in_logs`

**Per-failure statuses:** `log_fetch_failed`, `repaired`, `repair_failed`, `dry_run_complete`

### `orchestrator/__init__.py`

Exports `WorkflowOrchestrator` and `WorkflowResult`.

---

## 2. Configuration (`config/`)

### `config/settings.py`

Central `Settings` dataclass loaded from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | GitHub API token |
| `GITHUB_OWNER` | — | Repository owner |
| `GITHUB_REPO` | — | Repository name |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for LLM agents |
| `MAX_RETRY_ATTEMPTS` | `3` | Max repair retries per failure |
| `SAMPLE_PROJECTS_DIR` | `sample_projects` | Test discovery root |
| `DOCKER_IMAGE_TAG` | `self-healing-validator` | Validation image tag |
| `DOCKER_CLEANUP` | `true` | Remove image after validation |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

**Paths (computed):**

- `logs_dir` → `logs/`
- `results_dir` → `results/`
- `prompts_dir` → `config/prompts/`
- `failure_memory_path` → `results/failure_memory.json`

### `config/prompts/diagnosis.txt`

Replaces hardcoded prompt in `ReasoningAgent`. Placeholders: `{failure_context}`, `{failure_type}`.

### `config/prompts/patch.txt`

Replaces hardcoded prompt in `PatchAgent`. Placeholders: `{failure_context}`, `{diagnosis}`, `{target_file}`, `{current_file_content}`, `{source_context}`.

**Fix:** Diagnosis is now passed into patch generation (previously printed but unused).

---

## 3. Utilities (`utils/`)

### `utils/logging.py`

- `setup_logging()` — configures `self_healing` logger with timestamped format
- `get_logger(name)` — namespaced child loggers (e.g. `self_healing.orchestrator`)

Replaces `print()` across the pipeline.

### `utils/errors.py`

- `ErrorCategory` enum: `assertion_error`, `import_error`, `syntax_error`, `module_not_found`, `dependency_error`, `build_error`, `runtime_error`, `unknown`
- `categorize_failure(errors, validation_status)` — regex-based classification from log lines

### `utils/prompts.py`

- `load_prompt(template_name, variables)` — reads `config/prompts/{name}.txt` and applies `.format(**variables)`

### `utils/failure_memory.py`

Persistent JSON at `results/failure_memory.json`. Each record stores:

- `timestamp`, `run_id`, `failure_type`, `target_file`
- `diagnosis`, `generated_patch`, `validation_outcome`
- `attempt`, `success`

Methods: `record_repair()`, `get_repair_history()`, `get_failure_types()`

### `utils/discovery.py`

Moved `discover_sample_tests()` from `main.py` (same behavior).

### `utils/log_extractor.py`

- `save_and_extract_logs(zip_bytes, run_id)` — saves ZIP under `logs/`, extracts to `logs/extracted/{run_id}/`
- `iter_log_files(extract_dir)` — yields `(path, text)` for each log file

### `utils/docker_utils.py`

- `cleanup_validation_containers(image_tag)` — prunes containers and removes validation image when `DOCKER_CLEANUP=true`

### `utils/results_store.py`

- `save_run_result(run_id, payload)` — writes `results/run_{id}_{timestamp}.json`
- `save_metrics(metrics)` — appends to `results/metrics_summary.json` with aggregate counts

---

## 4. Agent Updates (backward compatible)

Public method signatures preserved; internals upgraded.

### `agents/monitoring_agent.py`

- Uses `get_settings()` instead of direct `os.getenv` / `load_dotenv`
- Structured logging instead of `print`
- Request timeouts added

### `agents/analysis_agent.py`

- Debug logging on extracted errors
- No API changes

### `agents/reasoning_agent.py`

- Prompt loaded via `load_prompt("diagnosis", ...)`
- New optional parameter: `failure_type: str = "unknown"`
- Uses centralized OpenAI model from settings

### `agents/patch_agent.py`

- Prompt loaded via `load_prompt("patch", ...)`
- New optional parameter: `diagnosis: str = ""` (fed into template)
- `_load_related_source()` generalized for any `project_*` directory (includes `project_3`)
- Uses settings for paths and model

### `agents/validation_agent.py`

- Configurable `image_tag` from settings
- Adds `category` field to validation results
- Calls `cleanup_validation_containers()` after build/run (success or failure)

### `agents/__init__.py` (new)

Re-exports all five agent classes.

---

## 5. Entry Point (`main.py`)

**Before:** 188-line procedural script with inline orchestration, `print()`, and global agent instances.

**After:** Thin entry point:

```python
orchestrator = WorkflowOrchestrator()
result = orchestrator.run()
```

- Calls `setup_logging()` on startup
- Returns exit code `0` on success or no failures, `1` otherwise
- Runnable via `python main.py`

---

## 6. Results Directory (`results/`)

| File | Written by | Contents |
|------|------------|----------|
| `failure_memory.json` | `FailureMemory` | All repair attempts (cumulative) |
| `run_{id}_{timestamp}.json` | `ResultsStore.save_run_result` | Single workflow outcome |
| `metrics_summary.json` | `ResultsStore.save_metrics` | Aggregated experiment metrics |

Runtime JSON files are **gitignored**; `.gitkeep` preserves the directory.

---

## 7. Dependency & Git Changes

### `requirements.txt`

- Added `openai>=1.0.0` (was imported but not listed)

### `.gitignore`

- Added `results/*.json` with exception for `results/.gitkeep`

---

## 8. Retry Logic

Configured via `MAX_RETRY_ATTEMPTS` (default 3).

On failed validation:

1. Validation output (truncated to 2000 chars) is appended to failure context
2. Next attempt re-diagnoses and re-patches with enriched context
3. Each attempt is recorded in failure memory regardless of outcome
4. Loop stops early on `validation.status == "success"`

---

## 9. Compatibility Notes

| Concern | Status |
|---------|--------|
| Agent class names and imports | Unchanged |
| `MonitoringAgent.get_failed_runs()` / `get_workflow_logs()` | Unchanged |
| `AnalysisAgent.extract_failure_context()` / `extract_failed_file()` | Unchanged |
| `ReasoningAgent.diagnose_failure()` | Extended with optional `failure_type` |
| `PatchAgent.generate_patch()` / `apply_patch()` | Extended with optional `diagnosis` |
| `ValidationAgent.validate_patch()` | Same return shape; adds optional `category` |
| Docker validation flow | Unchanged (`docker build` + `docker run --rm`) |
| Sample projects | Unchanged |

Existing code that instantiates agents directly continues to work. New code should use `WorkflowOrchestrator` for full pipeline execution.

---

## 10. Environment Variables (Quick Reference)

Copy `.env.example` to `.env` and fill in values.

```bash
# Required for live runs
GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
OPENAI_API_KEY=

# Optional tuning
OPENAI_MODEL=gpt-4o-mini
MAX_RETRY_ATTEMPTS=3
DOCKER_IMAGE_TAG=self-healing-validator
DOCKER_CLEANUP=true
LOG_LEVEL=INFO
SAMPLE_PROJECTS_DIR=sample_projects

# Safety
DRY_RUN=false
BACKUP_BEFORE_PATCH=true

# Multi-failure + LLM + validation scope
MAX_FAILED_RUNS=5
MAX_FAILURES_PER_RUN=10
STOP_ON_FIRST_SUCCESS=true
OPENAI_TIMEOUT=60
OPENAI_MAX_RETRIES=3
VALIDATE_FULL_REPO=false
```

---

## 11. Running the Framework

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Safe first run (no file writes, no Docker)
DRY_RUN=true python main.py

# Run unit tests
pytest tests/

# Full orchestrated pipeline
python main.py
```

Inspect outputs:

- Logs: console (structured) + `logs/`
- Failure memory: `results/failure_memory.json`
- Per-run results: `results/run_*.json`
- Metrics: `results/metrics_summary.json`
- File backups (during repair): `results/backups/{run_id}/`

---

## Files Modified

| File | Change |
|------|--------|
| `main.py` | Orchestrator entry point + config validation |
| `config/settings.py` | Added `dry_run`, `backup_before_patch` |
| `config/validation.py` | Startup validation (new) |
| `orchestrator/workflow.py` | Backup, restore, dry-run |
| `utils/file_backup.py` | Backup manager (new) |
| `.env.example` | Environment template (new) |
| `agents/monitoring_agent.py` | Settings + logging |
| `agents/analysis_agent.py` | Logging |
| `agents/reasoning_agent.py` | Dynamic prompts + failure_type |
| `agents/patch_agent.py` | Dynamic prompts + diagnosis input + project_3 |
| `agents/validation_agent.py` | Settings + cleanup + error category |
| `requirements.txt` | Added openai |
| `.gitignore` | Ignore results JSON and backups |

## Files Created

| Path |
|------|
| `orchestrator/__init__.py` |
| `orchestrator/workflow.py` |
| `config/__init__.py` |
| `config/settings.py` |
| `config/prompts/diagnosis.txt` |
| `config/prompts/patch.txt` |
| `utils/__init__.py` |
| `utils/logging.py` |
| `utils/errors.py` |
| `utils/prompts.py` |
| `utils/failure_memory.py` |
| `utils/discovery.py` |
| `utils/log_extractor.py` |
| `utils/docker_utils.py` |
| `utils/results_store.py` |
| `agents/__init__.py` |
| `results/.gitkeep` |
| `UPDATES.md` |
| `.env.example` |
| `config/validation.py` |
| `utils/file_backup.py` |

---

*Changelog maintained across orchestration and safety upgrades.*

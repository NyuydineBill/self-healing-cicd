# Self-Healing CI/CD

A multi-agent Python framework that detects GitHub Actions failures, diagnoses them with an LLM, generates patches, validates fixes in Docker, and optionally opens a pull request.

## Quick start

```bash
# Clone and install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — set GITHUB_* and OPENAI_API_KEY

# Safe trial (no file writes, no Docker)
DRY_RUN=true python main.py

# Full repair (requires Docker)
python main.py

# Pre-flight check (recommended before live runs)
python main.py check

# Run unit tests
pytest tests/
```

## Production deployment

Full-product flow for teams using GitHub Actions end-to-end.

### 1. One-time setup

```bash
cp .env.example .env
# Set GITHUB_* , OPENAI_API_KEY

# Verify environment
python main.py check
```

Add repository secret **`OPENAI_API_KEY`** on GitHub (Settings → Secrets → Actions).

### 2. Local operator (human approves each patch)

```bash
REQUIRE_APPROVAL=true
AUTO_APPROVE_PATCHES=false
GIT_ENABLED=false
python main.py
```

You will see a unified diff and `[y/N]` prompt before any file is modified.

### 3. Automated CI self-heal (opens PR)

Already configured in [.github/workflows/self-heal.yml](.github/workflows/self-heal.yml):

| Setting | CI value | Purpose |
|---------|----------|---------|
| `AUTO_APPROVE_PATCHES` | `true` | No stdin in Actions |
| `GIT_ENABLED` | `true` | Branch + PR |
| `EXCLUDED_WORKFLOW_NAMES` | Self-heal workflows | Avoid repair loops |

Push to `main` → **Test Pipeline** fails → **Self-Heal on Failure** runs → review PR → merge.

### 4. Offline repair (cached logs, no GitHub API)

```bash
# After a prior run downloaded logs to logs/extracted/{run_id}/
OFFLINE_MODE=true python main.py
```

### 5. Path policy

Only files under `ALLOWED_PATH_PREFIXES` (default `sample_projects/`) can be patched. Extend for your monorepo:

```bash
ALLOWED_PATH_PREFIXES=sample_projects/,src/tests/
```

### CLI commands

| Command | Description |
|---------|-------------|
| `python main.py` | Run full orchestrator |
| `python main.py check` | Pre-flight health check |
| `python -m config.check` | Same as check |

## Architecture

```mermaid
flowchart TB
    subgraph entry [Entry]
        MAIN[main.py]
        CFG[config/validation]
    end

    subgraph orch [orchestrator]
        WO[WorkflowOrchestrator]
        RETRY[Retry loop]
        MEM[(failure_memory.json)]
    end

    subgraph agents [Agents]
        MON[MonitoringAgent<br/>GitHub Actions API]
        ANA[AnalysisAgent<br/>log regex]
        REA[ReasoningAgent<br/>LLM diagnosis]
        PAT[PatchAgent<br/>LLM patch]
        VAL[ValidationAgent<br/>Docker pytest]
    end

    subgraph support [utils]
        LOG[logs/ ZIP extract]
        BAK[file backup]
        GIT[git branch + PR]
        RES[results/ metrics]
    end

    MAIN --> CFG --> WO
    WO --> MON
    MON -->|failed runs + logs| LOG
    LOG --> ANA
    ANA --> REA
    REA --> PAT
    PAT -->|apply patch| BAK
    PAT --> VAL
    VAL -->|pass/fail| RETRY
    RETRY --> REA
    RETRY --> MEM
    RETRY --> RES
    VAL -->|success + GIT_ENABLED| GIT
```

**Control flow (one failure):**

1. **Detect** — list failed workflow runs; download log ZIP  
2. **Analyze** — extract errors and target file from logs  
3. **Diagnose** — LLM explains root cause (prompt template)  
4. **Patch** — LLM rewrites target file using diagnosis  
5. **Validate** — Docker build + scoped `pytest`  
6. **Retry** — enrich context and repeat up to `MAX_RETRY_ATTEMPTS`  
7. **Publish** — optional git branch, commit, pull request  

| Package | Role |
|---------|------|
| `orchestrator/` | Agent coordination, retries, batch results |
| `agents/` | Monitoring, analysis, reasoning, patch, validation |
| `config/` | Settings, prompt templates, startup checks |
| `utils/` | Logging, backups, git, secrets masking, LLM retries |
| `results/` | JSON metrics and repair history |

See [UPDATES.md](UPDATES.md) for the full changelog.

---

## How people use this framework

The framework supports three usage modes. Pick one based on how much automation you want.

### Mode 1 — Research / thesis (local, safe)

**Who:** Students, evaluators, or developers exploring the pipeline.

**How:**

1. Configure `.env` with GitHub + OpenAI credentials.  
2. Run `DRY_RUN=true python main.py` to see diagnosis and generated patches **without** changing files or running Docker.  
3. Inspect `results/` and console logs for metrics and failure memory.  
4. Run `pytest tests/` to verify framework behavior without external services.

**Outcome:** Demonstrates multi-agent coordination and persistence; no risk to the repository.

### Mode 2 — Semi-automatic repair (local operator)

**Who:** A developer reacting to a failed CI run on their machine.

**How:**

1. Ensure Docker is running.  
2. Set `DRY_RUN=false`, `GIT_ENABLED=false` (or `true` for PR flow).  
3. Run `python main.py` after a GitHub Actions failure.  
4. Review patched files locally; run `pytest` manually if desired.  
5. Commit or discard changes yourself.

**Outcome:** Faster than manual debugging; human stays in the loop for merge decisions.

### Mode 3 — CI-attached self-healing (hands-off)

**Who:** A team that wants the repo to react when **Test Pipeline** fails.

**How:**

1. Add repository secret `OPENAI_API_KEY`.  
2. Keep [.github/workflows/self-heal.yml](.github/workflows/self-heal.yml) enabled (triggers on failed **Test Pipeline**).  
3. Set `GIT_ENABLED=true` in the workflow (already configured there).  
4. On failure: Actions runs `python main.py` → validate → push branch → open PR.  
5. A human reviews and merges the PR.

**Outcome:** Closest to “production”; still requires human PR review before `main` changes.

### Completing the project beyond a thesis demo

| Step | Action |
|------|--------|
| 1 | Document one real failed run in your write-up (before/after logs, `results/run_*.json`) |
| 2 | Run Mode 1 locally and capture screenshots or metrics |
| 3 | Run Mode 3 once on GitHub with `OPENAI_API_KEY` secret and a deliberate test failure |
| 4 | State limitations honestly (see below) — reviewers expect this |

The `sample_projects/` targets are **intentionally broken** demos. For a “completed” story, either fix one sample via the orchestrator or point the framework at a repo where your own CI failed.

---

## Environment variables

Copy [.env.example](.env.example). Key settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Live mode | Repo access + Actions logs |
| `GITHUB_OWNER` | Live mode | Repository owner |
| `GITHUB_REPO` | Live mode | Repository name |
| `OPENAI_API_KEY` | Always | LLM diagnosis and patching |
| `DRY_RUN` | No | `true` = no writes, no Docker |
| `GIT_ENABLED` | No | `true` = branch, commit, push, PR |
| `REQUIRE_APPROVAL` | No | `true` = prompt before apply (local) |
| `AUTO_APPROVE_PATCHES` | No | `true` = skip prompt (CI default) |
| `OFFLINE_MODE` | No | `true` = use `logs/extracted/` only |
| `ALLOWED_PATH_PREFIXES` | No | Comma-separated path allowlist |

## Git integration

When `GIT_ENABLED=true` and a repair validates successfully:

1. Creates branch `self-heal/run-{id}-{timestamp}`
2. Commits repaired files
3. Pushes to GitHub
4. Opens a PR (if `GIT_CREATE_PR=true`)

Requires a git repository with `GITHUB_TOKEN` push permission.

## CI integration

- **Unit tests:** [.github/workflows/test.yml](.github/workflows/test.yml) runs `pytest tests/`
- **Self-heal on failure:** [.github/workflows/self-heal.yml](.github/workflows/self-heal.yml) runs the orchestrator when **Test Pipeline** fails

## Outputs

| Path | Content |
|------|---------|
| `results/failure_memory.json` | Repair history |
| `results/run_*.json` | Per-run outcomes |
| `results/metrics_summary.json` | Aggregate metrics |
| `logs/` | Downloaded workflow logs |

---

## Limitations

This section summarizes what the framework **does not** guarantee. Useful for thesis evaluation and production planning.

### Scope and correctness

- **Sample-first design** — Target resolution assumes failures under `sample_projects/` and pytest-style logs. Arbitrary repos may need custom regex and discovery rules.
- **LLM unpredictability** — Patches can be wrong, incomplete, or stylistically odd even when validation passes (tests may not cover the real failure).
- **Single-repo, single-provider** — GitHub Actions only; no GitLab, Jenkins, or CircleCI.
- **No semantic code understanding** — Repairs are text-based (LLM + file replace), not AST-aware refactors.

### Operations

- **Docker required** for live validation — Not optional in non-dry-run mode.
- **API costs** — Every diagnosis and patch calls OpenAI; retries multiply usage.
- **No guaranteed PR merge** — Opens a PR; humans must review. No auto-merge.
- **Git state assumptions** — Git integration expects a clean enough repo; complex multi-branch workflows may need manual conflict resolution.

### Security and safety

- **Broad file write** — A bad patch overwrites the target file; backup/rollback mitigates but does not eliminate risk.
- **Token scope** — `GITHUB_TOKEN` needs Actions read and (for git mode) contents write. Leaked tokens expose the repo.
- **Secrets in logs** — Masking reduces risk; DEBUG logging can still expose sensitive context if enabled carelessly.

### CI behavior

- **Self-heal trigger** — Only reacts to failures of the workflow named **Test Pipeline**; rename requires updating `self-heal.yml`.
- **No infinite-loop protection beyond skipping PR events** — Repeated failures could open multiple PRs if not configured (`STOP_ON_FIRST_SUCCESS`, run limits).
- **First failures only by default** — `MAX_FAILED_RUNS` and `MAX_FAILURES_PER_RUN` cap work; very noisy pipelines may need tuning.

### Implemented product safeguards

- Human approval before apply (`REQUIRE_APPROVAL` / diff prompt)  
- Path allowlist (`ALLOWED_PATH_PREFIXES`)  
- Self-heal workflow excluded from triggers (loop guard)  
- GitHub API retry on rate limits  
- Pre-flight check (`python main.py check`)  

### Remaining gaps for enterprise adoption

- Pluggable log parsers per stack (Java, Go, etc.)  
- Staging integration tests against live GitHub/Docker  
- Auto-merge policy (optional, behind flag)  
- Web UI for approval instead of terminal prompt  

---

## License

See repository license file if present.

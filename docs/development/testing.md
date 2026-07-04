# Testing Guide

How to verify the self-healing CI/CD framework works end-to-end across every supported scenario.
No scenario requires all settings — start with the ones that match your environment.

---

## Prerequisites

```bash
# Clone and create virtualenv
git clone https://github.com/NyuydineBill/self-healing-cicd.git
cd self-healing-cicd
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env
```

Minimum `.env` for each scenario is listed in the table below.

| Scenario | OPENAI_API_KEY | GITHUB_TOKEN | GITHUB_OWNER / REPO | Docker |
|----------|:--------------:|:------------:|:-------------------:|:------:|
| 1. Unit tests | — | — | — | — |
| 2. Pre-flight check | — | — | — | — |
| 3. Local dry-run | ✓ | ✓ | ✓ | — |
| 4. Offline repair | ✓ | — | — | — |
| 5. Live repair (no Git) | ✓ | ✓ | ✓ | optional |
| 6. Live repair + PR | ✓ | ✓ | ✓ | optional |
| 7. Approval gate | ✓ | ✓ | ✓ | optional |
| 8. Web UI approval | ✓ | ✓ | ✓ | optional |
| 9. CI manual trigger (dry-run) | secret | secret | auto | — |
| 10. CI auto self-heal | secret | secret | auto | — |

---

## Scenario 1 — Unit Tests (no credentials needed)

Verifies all framework internals using mocked agents. No API key, no Docker, no GitHub.

```bash
pytest tests/ -v
```

Expected: **47 passed**. Coverage is reported per module; overall must exceed 40%.

Run a single test file:

```bash
pytest tests/test_orchestrator.py -v
pytest tests/test_policy.py -v
pytest tests/test_git_repair.py -v
```

---

## Scenario 2 — Pre-Flight Health Check

Validates your `.env` configuration before running a live repair. Checks env vars, prompt templates, writable directories, and (when applicable) Docker availability.

```bash
python main.py check
# or
python -m config.check
```

Read every line. Common failures and fixes:

| Message | Fix |
|---------|-----|
| `OPENAI_API_KEY not set` | Add key to `.env` |
| `GITHUB_TOKEN not set` | Add token to `.env` |
| `Prompt template missing` | Ensure `config/prompts/` files are present |
| `Docker not available` | Start Docker Desktop / daemon |
| `results/ not writable` | `mkdir -p results && chmod 755 results` |

The check exits `0` on success, non-zero on failure. Run it before every live test.

---

## Scenario 3 — Local Dry-Run (safe first test)

Connects to GitHub, downloads the latest failed run log, generates a diagnosis and patch — **but does not write any files or run Docker/validation**.

```bash
# .env minimum: OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
DRY_RUN=true python main.py
```

What to check:

- Console shows `Running in DRY_RUN mode`
- `AnalysisAgent` prints extracted errors and target file
- `ReasoningAgent` prints the LLM diagnosis
- `PatchAgent` prints the generated patch (not applied)
- Status: `dry_run_complete`
- `results/run_*.json` is written with `"dry_run": true`

If GitHub has no recent failures, trigger one first (see Scenario 10) or use offline mode (Scenario 4).

---

## Scenario 4 — Offline Repair (no GitHub API)

Repairs from locally cached logs — useful when you have a real log but no live GitHub connection, or when re-testing an already-downloaded run.

### Step 1 — Get a log (one-time)

Either do a normal run that downloads logs, or manually place a log:

```bash
# After any prior run that had failures, logs land here:
ls logs/extracted/
```

Or copy a real GitHub Actions log text into:

```
logs/extracted/999999/0_Test Pipeline.txt
```

### Step 2 — Run in offline mode

```bash
OFFLINE_MODE=true DRY_RUN=true python main.py   # read-only inspection
OFFLINE_MODE=true python main.py                 # full repair attempt
```

What to check:

- Console shows `Running in OFFLINE_MODE`
- Framework reads from `logs/extracted/` without calling GitHub API
- Repair proceeds normally from analysis onward

---

## Scenario 5 — Live Repair, No Git Integration

Connects to GitHub, downloads a real failed run, repairs the file, validates with command replay (or Docker fallback), and stops — no branch or PR is created.

```bash
GIT_ENABLED=false DRY_RUN=false python main.py
```

What to check:

- `MonitoringAgent` fetches a failed workflow run
- `AnalysisAgent` extracts target files and the failing command
- `ValidationAgent` replays the command (or runs Docker + pytest)
- Repaired file is written to disk
- `results/run_*.json` shows `"status": "repaired"` and `"repair_success": true`
- Running `pytest <target_dir>` manually passes after repair

To reset after the test:

```bash
git checkout -- sample_projects/   # discard repaired changes
```

---

## Scenario 6 — Live Repair + Pull Request

Full end-to-end: detect → diagnose → patch → validate → push branch → open PR.

```bash
GIT_ENABLED=true GIT_CREATE_PR=true DRY_RUN=false python main.py
```

What to check:

- Branch `self-heal/run-{id}-{timestamp}` is created and pushed
- PR is opened on GitHub with the repair diff
- PR body lists all repaired files and diagnosis summary
- `results/run_*.json` contains `git_info.pr_url`

**Prerequisite for PR creation:**
Settings → Actions → General → Workflow permissions → enable
**"Allow GitHub Actions to create and approve pull requests"**.
Or add a PAT with `repo` scope as `GITHUB_PR_TOKEN` in `.env`.

---

## Scenario 7 — Human Approval Gate (local)

Prompts you with a unified diff before writing any file. You type `y` to apply or `n` to reject.

```bash
REQUIRE_APPROVAL=true AUTO_APPROVE_PATCHES=false GIT_ENABLED=false python main.py
```

What to check:

- After patch generation, console shows a colored unified diff
- Prompt: `Apply this patch? [y/N]`
- Type `n` → file unchanged, run ends as `rejected`
- Type `y` → file written, validation runs, repair completes

---

## Scenario 8 — Web UI Approval

Opens a browser page where you click **Approve** or **Reject** instead of using the terminal prompt.

```bash
WEB_APPROVAL_ENABLED=true REQUIRE_APPROVAL=true AUTO_APPROVE_PATCHES=false python main.py
```

Browser opens automatically at `http://127.0.0.1:8765`.

Or start only the UI server (for testing the server itself):

```bash
python main.py approve-ui
# Custom port:
python main.py approve-ui 9000
```

What to check:

- Browser shows patch diff with Approve / Reject buttons
- Approve → repair continues; Reject → patch discarded
- `results/pending_approval.json` is created before the prompt, removed after decision

---

## Scenario 9 — CI Manual Trigger (workflow_dispatch, safe)

Tests the self-heal GitHub Actions workflow without needing a real CI failure. Runs as a dry-run so no files are changed.

### Setup (one-time)

1. Add `OPENAI_API_KEY` to **Settings → Secrets → Actions**.
2. Enable **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests**.

### Trigger

GitHub → **Actions** → **Self-Heal on Failure** → **Run workflow**

| Input | Value for safe test |
|-------|---------------------|
| `dry_run` | ✓ (checked) |
| `offline_mode` | unchecked |
| `git_enabled` | unchecked |

### What to check

- Workflow runs `python main.py check` (pre-flight) then `python main.py`
- Logs show diagnosis + patch generation
- No files are committed (dry-run)
- Status badge stays green

---

## Scenario 10 — Full CI Self-Heal (auto-trigger)

Push a deliberate test failure → **Test Pipeline** fails → **Self-Heal on Failure** triggers automatically → repair PR opened.

### Step 1 — Break a sample project

```bash
./scripts/break-sample.sh 1   # introduces assertion failure in project_1
git add sample_projects/
git commit -m "test: intentional CI failure in project_1"
git push origin main
```

### Step 2 — Watch the pipelines

1. **Test Pipeline** runs and fails (red ✗).
2. **Self-Heal on Failure** triggers automatically (~30 s later).
3. Self-Heal: downloads log → extracts failure → LLM diagnosis → patch → validate → push branch → open PR.

### Step 3 — Review the PR

- Open the PR created by the bot.
- Check: diff fixes the assertion, description contains diagnosis.
- Merge it → **Test Pipeline** turns green.

### Reset without merging

```bash
./scripts/reset-samples.sh
git add sample_projects/
git commit -m "chore: reset samples to golden state"
git push origin main
```

---

## Scenario 11 — Multi-File Repair (project_11)

Tests the multi-file patch path where the root cause spans `app.py` and the test file.

### Break it

```bash
# project_11 is already broken by design (in golden state it passes,
# but the import mismatch is the failure scenario — check SCENARIO.md)
cat sample_projects/project_11/SCENARIO.md

# Verify it fails:
pytest sample_projects/project_11/ -v
```

### Run the repair

```bash
GIT_ENABLED=false python main.py
```

What to check:

- `AnalysisAgent` identifies **both** `app.py` and the test file
- `PatchAgent` calls `generate_multi_patch()` → returns a JSON array with two `FilePatch` entries
- Both files are written atomically
- Validation replays `pytest sample_projects/project_11/ -v` and passes
- `results/run_*.json` shows `"target_files": ["sample_projects/project_11/app.py", "...test_multi_file.py"]`

---

## Scenario 12 — Sample Project Matrix

Run any of the 14 sample projects to verify specific failure categories.

| Project | Failure | How to trigger |
|---------|---------|----------------|
| `project_1` | AssertionError | `./scripts/break-sample.sh 1` |
| `project_2` | ImportError | `./scripts/break-sample.sh 2` |
| `project_3` | SyntaxError | `./scripts/break-sample.sh 3` |
| `project_4` | Logic bug (wrong result) | `./scripts/break-sample.sh 4` |
| `project_5` | ModuleNotFoundError | `./scripts/break-sample.sh 5` |
| `project_6` | AttributeError | `./scripts/break-sample.sh 6` |
| `project_7` | NameError | `./scripts/break-sample.sh 7` |
| `project_8` | IndexError | `./scripts/break-sample.sh 8` |
| `project_9` | TypeError (numeric) | `./scripts/break-sample.sh 9` |
| `project_10` | ZeroDivisionError | `./scripts/break-sample.sh 10` |
| `project_11` | Multi-file ImportError | already broken by design |
| `project_12` | Wrong exception type | already broken by design |
| `project_13` | Off-by-one | already broken by design |
| `project_14` | Type coercion TypeError | already broken by design |

Verify each project is broken before repair:

```bash
pytest sample_projects/project_N/ -v    # should FAIL
```

Run the repair, then verify it passes:

```bash
GIT_ENABLED=false python main.py
pytest sample_projects/project_N/ -v    # should PASS after repair
```

Reset all samples:

```bash
./scripts/reset-samples.sh
```

---

## Reading Results

After any repair run, inspect:

```bash
# Per-run outcome (status, attempts, git_info, repair_success)
cat results/run_*.json | python -m json.tool

# All repair history (cumulative)
cat results/failure_memory.json | python -m json.tool

# Aggregate metrics
cat results/metrics_summary.json | python -m json.tool

# Audit trail (every patch apply / reject / PR open)
cat results/audit.log
```

Key fields in `run_*.json`:

| Field | Meaning |
|-------|---------|
| `status` | `repaired`, `repair_failed`, `dry_run_complete`, `log_fetch_failed` |
| `repair_success` | `true` if validation passed |
| `target_files` | All files repaired in this run |
| `attempts[].validation.status` | `success` or `failure` per attempt |
| `git_info.branch` | Branch name created |
| `git_info.pr_url` | PR URL (if `GIT_CREATE_PR=true`) |

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `no_failures` status, nothing repaired | No failed GitHub runs found | Push a broken test (Scenario 10) or use `OFFLINE_MODE` |
| `KeyError` / API crash | GitHub API shape changed | Pull latest; check `monitoring_agent.py` |
| Validation always fails | Wrong command extracted | Set `LOG_LEVEL=DEBUG` to see the replayed command |
| PR not created (403) | Token missing PR permission | Add `GITHUB_PR_TOKEN` PAT or enable Actions setting |
| `EOFError` on approval | Stdin closed in CI | Set `AUTO_APPROVE_PATCHES=true` |
| `ModuleNotFoundError: self_healing` | Package not installed | Run from repo root; `pip install -e .` |
| Docker error in validation | Docker not running | Start Docker, or let command-replay handle it |

For more detail see [Troubleshooting](../guides/troubleshooting.md).

---

## Recommended Test Order

If you are testing for the first time or evaluating the framework:

1. `pytest tests/` — framework works at all
2. `python main.py check` — your env is configured
3. `DRY_RUN=true python main.py` — end-to-end path with real GitHub (read-only)
4. `./scripts/break-sample.sh 1 && GIT_ENABLED=false python main.py` — full local repair
5. Break a project → push → watch CI self-heal and open a PR (Scenario 10)

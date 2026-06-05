# Troubleshooting

## Pre-flight Check

Run `python main.py check` before anything else. It validates your tokens, Docker, and prompt templates and tells you exactly what is missing.

---

## Common Errors

### `ConfigurationError: GITHUB_TOKEN is not set`
Copy `.env.example` to `.env` and fill in `GITHUB_TOKEN`. The token needs `repo` and `actions:read` scopes at minimum.

### `ConfigurationError: OPENAI_API_KEY is not set`
Set `OPENAI_API_KEY=sk-...` in `.env`. Make sure the key is active and has sufficient quota.

### `403 Forbidden when opening PR`
The `GITHUB_TOKEN` provided to the workflow (via `secrets.GITHUB_TOKEN`) cannot create PRs on forks or may lack `pull-requests:write` scope. Set a separate `GITHUB_PR_TOKEN` in your `.env` (or GitHub Actions secret) using a Personal Access Token with `repo` scope.

### `Docker daemon not running`
The validation step builds and runs a Docker container.  Start Docker Desktop (Mac/Windows) or `sudo systemctl start docker` (Linux), then retry.

If Docker is unavailable and you only want to test diagnosis/patch generation, set `DRY_RUN=true` to skip validation entirely.

### `No failed workflow runs found`
- The target repo has no recent failed runs, or all failures are in workflows listed in `EXCLUDED_WORKFLOW_NAMES`.
- Make sure `GITHUB_OWNER` and `GITHUB_REPO` point to the correct repository.
- Try `OFFLINE_MODE=true` to replay a cached log: place a `workflow_logs.zip` in `logs/` and re-run.

### `FileNotFoundError: Prompt template not found`
The `config/prompts/` directory is missing `diagnosis.txt` or `patch.txt`. These templates ship with the repo — check that you cloned the full repository and haven't deleted them.

### `Patch approved but test still fails after repair`
The validation scope may be too narrow (`VALIDATE_FULL_REPO=false`). Set `VALIDATE_FULL_REPO=true` to run the full test suite inside Docker, or increase `MAX_RETRY_ATTEMPTS` to give the LLM more chances to converge.

### `LLM request failed after N attempt(s)`
Check your OpenAI API key quota and rate limits. Increase `OPENAI_TIMEOUT` (default 60 s) or `OPENAI_MAX_RETRIES` (default 3) in `.env`.

### `ruff check` or `mypy` fails in CI
Run `ruff check .` and `mypy agents/ config/ orchestrator/ parsers/ utils/ main.py` locally and fix any errors before pushing. CI mirrors these exact commands.

### Web approval UI not reachable
The UI binds to `127.0.0.1:<WEB_APPROVAL_PORT>`. It is intentionally loopback-only. If you're running inside a container or remote SSH session, you'll need port forwarding: `ssh -L 8765:localhost:8765 user@host`.

---

## Log Locations

| Path | Contents |
|------|----------|
| `logs/self_healing.log` | Rotating application log (5 MB × 5 backups) |
| `results/run_<id>_<ts>.json` | Full output of each repair attempt |
| `results/metrics_summary.json` | Aggregate success/failure counts |
| `results/failure_memory.json` | Per-file repair history used to enrich retries |
| `results/audit.log` | Append-only record of every patch write, rejection, and PR |

---

## Getting More Detail

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output including patch previews (also set `LOG_PATCH_PREVIEW_CHARS=500`).

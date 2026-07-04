# Nyuydine Platform — Phase 1

> Part of the [project documentation](../README.md).

Hosted GitHub Reliability Engine built on the existing self-healing orchestrator.

## What ships in Phase 1

- **GitHub App webhook** — queues repair when a workflow run fails
- **Adapter interfaces** — `PipelineAdapter`, `RepoAdapter`, `LLMAdapter` (GitHub + OpenAI only)
- **REST API** — trigger/list/get repairs, approve/reject patches, usage metrics
- **Celery worker** — clones repo, runs orchestrator, persists results
- **Automation modes** — `observation`, `suggest`, `auto_pr`

Dashboard and additional CI providers are Phase 2+ (see [`docs/product/prompts/mvp.txt`](../product/prompts/mvp.txt)).

## Quick start (local)

```bash
# Install platform dependencies
pip install -r requirements-platform.txt

# Configure (copy and edit)
cp .env.platform.example .env
# Same template: docs/platform/env.example
# Add OPENAI_API_KEY at minimum

# Run API with in-process repairs (no Redis required)
export CELERY_TASK_ALWAYS_EAGER=true
export DATABASE_URL=sqlite:///./platform_data/nyuydine.db

python -m nyuydine.main
```

API: http://localhost:8080/health

## Quick start (Docker)

```bash
export OPENAI_API_KEY=sk-...
export GITHUB_APP_ID=...
export GITHUB_APP_PRIVATE_KEY="$(cat your-app.pem)"
export GITHUB_WEBHOOK_SECRET=...

docker compose -f docker-compose.platform.yml up --build
```

## GitHub App setup

1. Create a GitHub App (Settings → Developer settings → GitHub Apps)
2. Permissions:
   - **Actions**: Read
   - **Contents**: Read & write (for PRs in `auto_pr` mode)
   - **Pull requests**: Read & write
   - **Metadata**: Read
3. Subscribe to events: **Workflow run**
4. Webhook URL: `https://<your-host>/webhooks/github`
5. Install the app on target repositories

## API overview

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `POST /webhooks/github` | GitHub App events |
| `GET /api/v1/repairs` | List repair runs |
| `GET /api/v1/repairs/{id}` | Repair detail + attempts |
| `POST /api/v1/repairs/trigger` | Manually queue a repair |
| `POST /api/v1/repairs/{id}/approve` | Approve/reject pending patch (`suggest` mode) |
| `GET /api/v1/organizations/{id}/usage` | Repair usage counter |

If `PLATFORM_API_KEY` is set, pass header: `X-API-Key: <key>`

## Automation modes

| Mode | Behavior |
|------|----------|
| `observation` | Diagnose + generate patch, no file writes (`DRY_RUN`) |
| `suggest` | Generate patch, wait for API approval, apply if approved |
| `auto_pr` | Auto-apply, validate, commit, open PR |

Set per-organization default in DB, or override per repair trigger.

## Architecture

```
GitHub webhook → API → Celery queue → Worker
                              ↓
                    clone repo (GitHubRepoAdapter)
                              ↓
                    WorkflowOrchestrator (existing agents)
                              ↓
                    PostgreSQL / SQLite (repair runs, usage)
```

Adapters live in `nyuydine/adapters/`. The orchestrator is unchanged; the worker configures it via environment variables per job.

## Project layout

```
nyuydine/
  adapters/     # Pipeline, repo, LLM interfaces + GitHub/OpenAI
  api/          # FastAPI routes
  db/           # SQLAlchemy models
  services/     # repair execution, GitHub App auth, approval
  workers/      # Celery tasks
```

## CLI still works

The original `python main.py` flow is unchanged for local development and CI.

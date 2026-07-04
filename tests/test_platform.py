import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nyuydine.adapters.base import AutomationMode
from nyuydine.adapters.github_pipeline import GitHubActionsAdapter
from nyuydine.api.app import create_app
from nyuydine.config import PlatformSettings, get_platform_settings
from nyuydine.db.session import SessionLocal, init_db, reset_engine
from nyuydine.services.approval import automation_env
from nyuydine.services.github_app import verify_webhook_signature
from nyuydine.services.repair_service import (
    _workspace_path,
    get_or_create_org,
    get_or_create_repository,
)


@pytest.fixture
def platform_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("PLATFORM_API_KEY", "test-key")
    get_platform_settings.cache_clear()
    reset_engine()
    yield
    get_platform_settings.cache_clear()
    reset_engine()


@pytest.fixture
def db(platform_settings):
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(platform_settings):
    reset_engine()
    init_db()
    return TestClient(create_app())


def test_workspace_path_is_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _workspace_path(Path("workspaces"), "acme", "acme/app")
    assert path.is_absolute()
    assert path.name == "acme_app"
    assert path.parent.name == "acme"


def test_automation_env_modes():
    assert automation_env(AutomationMode.OBSERVATION)["DRY_RUN"] == "true"
    assert automation_env(AutomationMode.AUTO_PR)["GIT_ENABLED"] == "true"
    assert automation_env(AutomationMode.SUGGEST)["AUTO_APPROVE_PATCHES"] == "false"


def test_webhook_signature():
    body = b'{"hello": "world"}'
    secret = "test-secret"
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    with patch("nyuydine.services.github_app.get_platform_settings") as mock_settings:
        mock_settings.return_value = PlatformSettings(github_webhook_secret=secret)
        assert verify_webhook_signature(body, sig) is True
        assert verify_webhook_signature(body, "sha256=invalid") is False


def test_github_pipeline_adapter_normalizes_run():
    adapter = GitHubActionsAdapter(token="token", owner="acme", repo="app")
    run = adapter._normalize_run(
        {
            "id": 12345,
            "name": "CI",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/acme/app/actions/runs/12345",
        }
    )
    assert run.run_id == "12345"
    assert run.conclusion == "failure"
    assert adapter.is_repairable(run) is True


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_github_webhook_ping(client):
    body = json.dumps({"zen": "test"}).encode()
    sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "pong"


def test_github_webhook_ignores_self_heal_workflow(client):
    payload = {
        "action": "completed",
        "installation": {"id": 1, "account": {"login": "acme"}},
        "repository": {
            "name": "app",
            "full_name": "acme/app",
            "owner": {"login": "acme"},
            "default_branch": "main",
        },
        "workflow_run": {
            "id": 999,
            "name": "Self-Heal on Failure",
            "conclusion": "failure",
        },
    }
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["ignored"] is True
    assert response.json()["reason"] == "excluded workflow"


def test_create_org_and_repository(db):
    org = get_or_create_org(db, name="Acme", slug="acme")
    repo = get_or_create_repository(
        db,
        organization=org,
        installation_id=999,
        owner="acme",
        name="app",
        full_name="acme/app",
    )
    assert repo.organization_id == org.id
    assert repo.full_name == "acme/app"


def test_list_repairs_requires_api_key_when_configured(client):
    response = client.get("/api/v1/repairs")
    assert response.status_code == 401

    response = client.get("/api/v1/repairs", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == []


@patch("nyuydine.api.routes.repairs.enqueue_repair", return_value="task-123")
def test_trigger_repair(mock_enqueue, client, db):
    org = get_or_create_org(db, name="Acme", slug="acme")
    repo = get_or_create_repository(
        db,
        organization=org,
        installation_id=1,
        owner="acme",
        name="app",
        full_name="acme/app",
    )

    response = client.post(
        "/api/v1/repairs/trigger",
        headers={"X-API-Key": "test-key"},
        json={
            "repository_id": repo.id,
            "pipeline_run_id": "123456",
            "workflow_name": "CI",
            "automation_mode": "observation",
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["pipeline_run_id"] == "123456"
    assert payload["status"] == "queued"
    mock_enqueue.assert_called_once()

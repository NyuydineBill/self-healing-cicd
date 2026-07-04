from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from nyuydine.api.deps import DbSession
from nyuydine.db.models import RepairRun, RepairStatus
from nyuydine.services.github_app import parse_repository, verify_webhook_signature
from nyuydine.services.repair_service import (
    create_repair_run,
    get_or_create_org,
    get_or_create_repository,
)
from nyuydine.workers.tasks import enqueue_repair
from utils.logging import get_logger

logger = get_logger("github_webhook")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(request: Request, db: Session = DbSession) -> dict:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event == "ping":
        return {"ok": True, "message": "pong"}

    if event != "workflow_run":
        return {"ok": True, "ignored": True, "event": event}

    action = payload.get("action")
    workflow_run = payload.get("workflow_run") or {}
    if action != "completed" or workflow_run.get("conclusion") != "failure":
        return {"ok": True, "ignored": True, "reason": "not a failed completion"}

    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    if not installation_id:
        raise HTTPException(status_code=400, detail="Missing installation id")

    owner, name, full_name = parse_repository(payload)
    account = (installation.get("account") or {}).get("login") or owner
    org = get_or_create_org(db, name=account, slug=account)
    repository = get_or_create_repository(
        db,
        organization=org,
        installation_id=int(installation_id),
        owner=owner,
        name=name,
        full_name=full_name,
        default_branch=(payload.get("repository") or {}).get("default_branch", "main"),
    )

    pipeline_run_id = str(workflow_run.get("id"))
    workflow_name = workflow_run.get("name")

    existing = (
        db.query(RepairRun)
        .filter(
            RepairRun.repository_id == repository.id,
            RepairRun.pipeline_run_id == pipeline_run_id,
        )
        .one_or_none()
    )
    if existing and existing.status not in (RepairStatus.FAILED, RepairStatus.CANCELLED):
        return {"ok": True, "repair_run_id": existing.id, "deduplicated": True}

    repair_run = create_repair_run(
        db,
        repository=repository,
        pipeline_run_id=pipeline_run_id,
        workflow_name=workflow_name,
        automation_mode=org.automation_mode,
    )
    task_id = enqueue_repair(repair_run.id)
    repair_run.celery_task_id = task_id
    db.commit()

    logger.info(
        "Queued repair %s for %s run %s",
        repair_run.id,
        full_name,
        pipeline_run_id,
    )
    return {"ok": True, "repair_run_id": repair_run.id, "task_id": task_id}

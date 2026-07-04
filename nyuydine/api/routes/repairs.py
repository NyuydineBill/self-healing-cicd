from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from nyuydine.adapters.base import AutomationMode
from nyuydine.api.deps import ApiAuth, DbSession, parse_result_json
from nyuydine.db.models import RepairRun, RepairStatus, Repository
from nyuydine.schemas.repairs import (
    ApproveRepairRequest,
    OrganizationSummary,
    RepairRunDetail,
    RepairRunSummary,
    RepositorySummary,
    TriggerRepairRequest,
    UsageSummary,
)
from nyuydine.services.approval import apply_decision, is_preapproved
from nyuydine.services.repair_service import create_repair_run
from nyuydine.services.usage import get_usage_total
from nyuydine.workers.tasks import enqueue_repair

router = APIRouter(prefix="/api/v1", tags=["repairs"], dependencies=[ApiAuth])


def _to_summary(repair_run: RepairRun) -> RepairRunSummary:
    return RepairRunSummary(
        id=repair_run.id,
        organization_id=repair_run.organization_id,
        repository_id=repair_run.repository_id,
        pipeline_run_id=repair_run.pipeline_run_id,
        workflow_name=repair_run.workflow_name,
        status=repair_run.status.value,
        automation_mode=repair_run.automation_mode.value,
        repair_success=repair_run.repair_success,
        message=repair_run.message,
        pr_url=repair_run.pr_url,
        created_at=repair_run.created_at,
        updated_at=repair_run.updated_at,
        completed_at=repair_run.completed_at,
    )


def _to_detail(repair_run: RepairRun) -> RepairRunDetail:
    pending = parse_result_json(repair_run.result_json)
    attempts = [
        {
            "attempt_number": a.attempt_number,
            "failure_type": a.failure_type,
            "target_file": a.target_file,
            "validation_status": a.validation_status,
            "success": a.success,
        }
        for a in repair_run.attempts
    ]
    return RepairRunDetail(
        **_to_summary(repair_run).model_dump(),
        result_json=pending,
        attempts=attempts,
    )


@router.get("/repairs", response_model=list[RepairRunSummary])
def list_repairs(
    db: Session = DbSession,
    organization_id: str | None = None,
    limit: int = 50,
) -> list[RepairRunSummary]:
    query = db.query(RepairRun).order_by(RepairRun.created_at.desc())
    if organization_id:
        query = query.filter(RepairRun.organization_id == organization_id)
    return [_to_summary(r) for r in query.limit(limit).all()]


@router.get("/repairs/{repair_id}", response_model=RepairRunDetail)
def get_repair(repair_id: str, db: Session = DbSession) -> RepairRunDetail:
    repair_run = db.get(RepairRun, repair_id)
    if not repair_run:
        raise HTTPException(status_code=404, detail="Repair run not found")
    return _to_detail(repair_run)


@router.post(
    "/repairs/trigger", response_model=RepairRunSummary, status_code=status.HTTP_202_ACCEPTED
)
def trigger_repair(body: TriggerRepairRequest, db: Session = DbSession) -> RepairRunSummary:
    repository = db.get(Repository, body.repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    mode = None
    if body.automation_mode:
        try:
            mode = AutomationMode(body.automation_mode)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid automation_mode: {body.automation_mode}"
            ) from exc

    repair_run = create_repair_run(
        db,
        repository=repository,
        pipeline_run_id=body.pipeline_run_id,
        workflow_name=body.workflow_name,
        automation_mode=mode,
    )
    task_id = enqueue_repair(repair_run.id)
    repair_run.celery_task_id = task_id
    db.commit()
    db.refresh(repair_run)
    return _to_summary(repair_run)


@router.post("/repairs/{repair_id}/approve", response_model=RepairRunDetail)
def approve_repair(
    repair_id: str,
    body: ApproveRepairRequest,
    db: Session = DbSession,
) -> RepairRunDetail:
    repair_run = db.get(RepairRun, repair_id)
    if not repair_run:
        raise HTTPException(status_code=404, detail="Repair run not found")

    if repair_run.status == RepairStatus.FAILED and body.approved and is_preapproved(repair_run):
        repair_run.status = RepairStatus.QUEUED
        repair_run.message = "Resuming approved repair"
        repair_run.completed_at = None
        task_id = enqueue_repair(repair_run.id)
        repair_run.celery_task_id = task_id
        db.commit()
        db.refresh(repair_run)
        return _to_detail(repair_run)

    if repair_run.status != RepairStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Repair is not awaiting approval (status={repair_run.status.value})",
        )
    try:
        repair_run = apply_decision(db, repair_run, approved=body.approved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.approved:
        task_id = enqueue_repair(repair_run.id)
        repair_run.celery_task_id = task_id
        db.commit()
        db.refresh(repair_run)
    return _to_detail(repair_run)


@router.get("/organizations", response_model=list[OrganizationSummary])
def list_organizations(db: Session = DbSession) -> list[OrganizationSummary]:
    from nyuydine.db.models import Organization

    return [
        OrganizationSummary(
            id=o.id,
            name=o.name,
            slug=o.slug,
            automation_mode=o.automation_mode.value,
        )
        for o in db.query(Organization).order_by(Organization.created_at.desc()).all()
    ]


@router.get("/repositories", response_model=list[RepositorySummary])
def list_repositories(
    db: Session = DbSession,
    organization_id: str | None = None,
) -> list[RepositorySummary]:
    query = db.query(Repository).order_by(Repository.created_at.desc())
    if organization_id:
        query = query.filter(Repository.organization_id == organization_id)
    return [
        RepositorySummary(
            id=r.id,
            organization_id=r.organization_id,
            full_name=r.full_name,
            owner=r.owner,
            name=r.name,
            default_branch=r.default_branch,
            is_active=r.is_active,
        )
        for r in query.all()
    ]


@router.get("/organizations/{org_id}/usage", response_model=UsageSummary)
def organization_usage(org_id: str, db: Session = DbSession) -> UsageSummary:
    return UsageSummary(
        organization_id=org_id,
        repairs_total=get_usage_total(db, org_id, "repairs"),
    )

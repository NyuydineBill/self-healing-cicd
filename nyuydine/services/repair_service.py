import json
import os
import re
import shutil
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import get_settings, reset_settings
from nyuydine.adapters.base import AutomationMode
from nyuydine.adapters.registry import get_default_registry
from nyuydine.config import get_platform_settings
from nyuydine.db.models import (
    Organization,
    RepairAttemptRecord,
    RepairRun,
    RepairStatus,
    Repository,
)
from nyuydine.services.approval import (
    automation_env,
    clear_approval_gate,
    install_approval_gate,
    is_preapproved,
)
from nyuydine.services.github_app import get_installation_token
from nyuydine.services.usage import record_usage
from orchestrator.workflow import BatchWorkflowResult, WorkflowOrchestrator
from utils.logging import get_logger

logger = get_logger("repair_service")

# Eager-mode repairs run in background threads; orchestrator mutates process cwd/env.
_repair_execution_lock = threading.Lock()


def _workspace_path(workspace_root: Path, org_slug: str, repository_full_name: str) -> Path:
    root = workspace_root if workspace_root.is_absolute() else (Path.cwd() / workspace_root)
    return (root / org_slug / repository_full_name.replace("/", "_")).resolve()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


def get_or_create_org(db: Session, *, name: str, slug: str | None = None) -> Organization:
    slug = slug or _slugify(name)
    settings = get_platform_settings()
    try:
        default_mode = AutomationMode(settings.default_automation_mode)
    except ValueError:
        default_mode = AutomationMode.SUGGEST

    org = db.query(Organization).filter(Organization.slug == slug).one_or_none()
    if org:
        if org.automation_mode != default_mode:
            org.automation_mode = default_mode
            db.commit()
            db.refresh(org)
        return org
    org = Organization(name=name, slug=slug, automation_mode=default_mode)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_or_create_repository(
    db: Session,
    *,
    organization: Organization,
    installation_id: int,
    owner: str,
    name: str,
    full_name: str,
    default_branch: str = "main",
) -> Repository:
    repo = (
        db.query(Repository)
        .filter(
            Repository.github_installation_id == installation_id,
            Repository.full_name == full_name,
        )
        .one_or_none()
    )
    if repo:
        if repo.organization_id != organization.id:
            repo.organization_id = organization.id
            db.commit()
        return repo

    repo = Repository(
        organization_id=organization.id,
        github_installation_id=installation_id,
        owner=owner,
        name=name,
        full_name=full_name,
        default_branch=default_branch,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def create_repair_run(
    db: Session,
    *,
    repository: Repository,
    pipeline_run_id: str,
    workflow_name: str | None = None,
    automation_mode: AutomationMode | None = None,
) -> RepairRun:
    org = repository.organization
    mode = automation_mode or org.automation_mode
    repair_run = RepairRun(
        organization_id=org.id,
        repository_id=repository.id,
        pipeline_run_id=str(pipeline_run_id),
        workflow_name=workflow_name,
        status=RepairStatus.QUEUED,
        automation_mode=mode,
    )
    db.add(repair_run)
    db.commit()
    db.refresh(repair_run)
    return repair_run


@contextmanager
def _job_environment(env: dict[str, str], workspace: Path) -> Generator[None, None, None]:
    previous = {key: os.environ.get(key) for key in env}
    original_cwd = os.getcwd()
    try:
        for key, value in env.items():
            os.environ[key] = value
        reset_settings()
        os.chdir(workspace)
        yield
    finally:
        os.chdir(original_cwd)
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        reset_settings()


def _serialize_batch(batch: BatchWorkflowResult) -> dict:
    return {
        "status": batch.status,
        "message": batch.message,
        "repair_success": batch.repair_success,
        "results": [
            {
                "run_id": r.run_id,
                "status": r.status,
                "message": r.message,
                "failure_type": r.failure_type,
                "target_file": r.target_file,
                "target_files": r.target_files,
                "repair_success": r.repair_success,
                "git_info": r.git_info,
                "attempts": [
                    {
                        "attempt": a.attempt,
                        "failure_type": a.failure_type,
                        "target_file": a.target_file,
                        "diagnosis": a.diagnosis,
                        "validation_status": a.validation.get("status"),
                        "success": a.success,
                    }
                    for a in r.attempts
                ],
            }
            for r in batch.results
        ],
    }


def execute_repair_run(db: Session, repair_run_id: str) -> RepairRun:
    settings = get_platform_settings()
    repair_run = db.get(RepairRun, repair_run_id)
    if not repair_run:
        raise ValueError(f"Repair run not found: {repair_run_id}")

    repository = repair_run.repository
    org = repair_run.organization

    repair_run.status = RepairStatus.RUNNING
    repair_run.message = "Repair job started"
    db.commit()

    workspace = _workspace_path(settings.workspace_root, org.slug, repository.full_name)
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    token = get_installation_token(repository.github_installation_id)
    registry = get_default_registry(
        token=token,
        owner=repository.owner,
        repo=repository.name,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
    )

    branch = repository.default_branch or registry.repo.default_branch()
    registry.repo.clone(str(workspace), branch=branch)

    mode_env = automation_env(repair_run.automation_mode)
    job_env = {
        "GITHUB_TOKEN": token,
        "GITHUB_PR_TOKEN": token,
        "GITHUB_OWNER": repository.owner,
        "GITHUB_REPO": repository.name,
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_MODEL": settings.openai_model,
        "GITHUB_TRIGGER_RUN_ID": repair_run.pipeline_run_id,
        "MAX_FAILED_RUNS": "1",
        "STOP_ON_FIRST_SUCCESS": "true",
        "GIT_BASE_BRANCH": branch,
        "ALLOWED_PATH_PREFIXES": "auto",
        "EXCLUDED_WORKFLOW_NAMES": ",".join(get_settings().excluded_workflow_names),
        **mode_env,
    }
    target_names = get_settings().target_workflow_names
    if target_names:
        job_env["TARGET_WORKFLOW_NAMES"] = ",".join(target_names)

    preapproved = is_preapproved(repair_run)

    if repair_run.automation_mode == AutomationMode.SUGGEST and not preapproved:
        install_approval_gate(db, repair_run)
    elif preapproved:
        job_env["AUTO_APPROVE_PATCHES"] = "true"
        job_env["REQUIRE_APPROVAL"] = "false"

    with _repair_execution_lock:
        try:
            with _job_environment(job_env, workspace):
                batch = WorkflowOrchestrator().run()
        finally:
            clear_approval_gate()

    _persist_batch_results(db, repair_run, batch)
    record_usage(
        db,
        organization_id=org.id,
        metric="repairs",
        repair_run_id=repair_run.id,
    )
    return repair_run


def _persist_batch_results(db: Session, repair_run: RepairRun, batch: BatchWorkflowResult) -> None:
    db.refresh(repair_run)
    if repair_run.status in (RepairStatus.AWAITING_APPROVAL, RepairStatus.CANCELLED):
        return

    payload = _serialize_batch(batch)
    dry_run_ok = any(r.status == "dry_run_complete" for r in batch.results)
    repair_run.result_json = json.dumps(payload)
    repair_run.completed_at = datetime.now(UTC)

    if repair_run.automation_mode == AutomationMode.OBSERVATION and dry_run_ok:
        repair_run.repair_success = True
        repair_run.message = "Observation complete: diagnosis and patch generated (not applied)."
        repair_run.status = RepairStatus.COMPLETED
    elif batch.repair_success:
        repair_run.repair_success = True
        repair_run.message = batch.message
        repair_run.status = RepairStatus.COMPLETED
        for result in batch.results:
            pr_url = (result.git_info or {}).get("pr_url")
            if pr_url:
                repair_run.pr_url = pr_url
                break
    elif dry_run_ok:
        repair_run.repair_success = False
        repair_run.message = batch.message
        repair_run.status = RepairStatus.COMPLETED
    else:
        repair_run.repair_success = False
        repair_run.message = batch.message
        repair_run.status = RepairStatus.FAILED

    for result in batch.results:
        for attempt in result.attempts:
            db.add(
                RepairAttemptRecord(
                    repair_run_id=repair_run.id,
                    attempt_number=attempt.attempt,
                    failure_type=attempt.failure_type,
                    target_file=attempt.target_file,
                    diagnosis=attempt.diagnosis,
                    validation_status=attempt.validation.get("status"),
                    success=attempt.success,
                )
            )

    db.commit()
    db.refresh(repair_run)

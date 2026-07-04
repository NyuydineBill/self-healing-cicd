import json
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from nyuydine.adapters.base import AutomationMode
from nyuydine.db.models import RepairRun, RepairStatus
from utils.approval import format_patch_diff, set_approval_hook
from utils.logging import get_logger

logger = get_logger("platform_approval")

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


def _save_pending_approval(
    db: Session,
    repair_run: RepairRun,
    *,
    target_file: str,
    diff: str,
) -> None:
    payload = {
        "target_file": target_file,
        "diff": diff,
        "decision": PENDING,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    repair_run.result_json = json.dumps({"pending_approval": payload})
    repair_run.status = RepairStatus.AWAITING_APPROVAL
    repair_run.message = f"Awaiting approval for patch to {target_file}"
    db.commit()


def wait_for_platform_approval(
    db: Session,
    repair_run_id: str,
    *,
    timeout_seconds: int = 600,
    poll_interval: float = 2.0,
) -> str | None:
    """Poll until approve/reject API updates the repair run. Returns decision or None on timeout."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        db.expire_all()
        repair_run = db.get(RepairRun, repair_run_id)
        if not repair_run or not repair_run.result_json:
            time.sleep(poll_interval)
            continue
        try:
            data = json.loads(repair_run.result_json)
        except json.JSONDecodeError:
            time.sleep(poll_interval)
            continue
        pending = data.get("pending_approval") or {}
        decision = pending.get("decision", PENDING)
        if decision == APPROVED:
            return APPROVED
        if decision == REJECTED:
            return REJECTED
        time.sleep(poll_interval)
    return None


def install_approval_gate(
    db: Session, repair_run: RepairRun, *, timeout_seconds: int = 600
) -> None:
    """Block orchestrator approval on platform API approve/reject."""

    def hook(
        target_file: str,
        original_content: str,
        patch_content: str,
        run_id: str | int = "",
    ) -> bool:
        diff = format_patch_diff(target_file, original_content, patch_content)
        _save_pending_approval(db, repair_run, target_file=target_file, diff=diff)
        logger.info(
            "Repair %s awaiting platform approval for %s (pipeline run %s)",
            repair_run.id,
            target_file,
            run_id,
        )
        decision = wait_for_platform_approval(
            db,
            repair_run.id,
            timeout_seconds=timeout_seconds,
        )
        if decision == APPROVED:
            repair_run.status = RepairStatus.RUNNING
            db.commit()
            return True
        logger.info("Repair %s patch rejected or timed out", repair_run.id)
        return False

    set_approval_hook(hook)


def clear_approval_gate() -> None:
    set_approval_hook(None)


def automation_env(mode: AutomationMode) -> dict[str, str]:
    """Map automation mode to framework environment variables."""
    if mode == AutomationMode.OBSERVATION:
        return {
            "DRY_RUN": "true",
            "REQUIRE_APPROVAL": "true",
            "AUTO_APPROVE_PATCHES": "false",
            "GIT_ENABLED": "false",
        }
    if mode == AutomationMode.AUTO_PR:
        return {
            "DRY_RUN": "false",
            "REQUIRE_APPROVAL": "true",
            "AUTO_APPROVE_PATCHES": "true",
            "GIT_ENABLED": "true",
            "GIT_CREATE_PR": "true",
        }
    # suggest
    return {
        "DRY_RUN": "false",
        "REQUIRE_APPROVAL": "true",
        "AUTO_APPROVE_PATCHES": "false",
        "GIT_ENABLED": "false",
    }


def is_preapproved(repair_run: RepairRun) -> bool:
    """True when operator already approved via the API (resume after restart)."""
    if not repair_run.result_json:
        return False
    try:
        data = json.loads(repair_run.result_json)
    except json.JSONDecodeError:
        return False
    pending = data.get("pending_approval") or {}
    return pending.get("decision") == APPROVED


def apply_decision(
    db: Session,
    repair_run: RepairRun,
    *,
    approved: bool,
) -> RepairRun:
    if repair_run.status != RepairStatus.AWAITING_APPROVAL:
        raise ValueError(f"Repair run is not awaiting approval (status={repair_run.status})")
    if not repair_run.result_json:
        raise ValueError("No pending approval payload found")

    data = json.loads(repair_run.result_json)
    pending = data.get("pending_approval")
    if not pending:
        raise ValueError("No pending approval payload found")

    pending["decision"] = APPROVED if approved else REJECTED
    pending["decided_at"] = datetime.now(UTC).isoformat()
    data["pending_approval"] = pending
    repair_run.result_json = json.dumps(data)
    if not approved:
        repair_run.status = RepairStatus.CANCELLED
        repair_run.message = "Patch rejected by operator"
        repair_run.completed_at = datetime.now(UTC)
    else:
        repair_run.status = RepairStatus.QUEUED
        repair_run.message = "Patch approved — resuming repair"
    db.commit()
    db.refresh(repair_run)
    return repair_run

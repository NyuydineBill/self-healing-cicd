import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from nyuydine.config import get_platform_settings
from nyuydine.db.models import RepairRun, RepairStatus
from nyuydine.db.session import SessionLocal
from nyuydine.services.repair_service import execute_repair_run
from nyuydine.workers.celery_app import celery_app
from utils.logging import get_logger

logger = get_logger("repair_task")


@celery_app.task(name="nyuydine.workers.run_repair", bind=True)
def run_repair(self: Any, repair_run_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        repair_run = execute_repair_run(db, repair_run_id)
        return {
            "repair_run_id": repair_run.id,
            "status": repair_run.status.value,
            "repair_success": repair_run.repair_success,
            "message": repair_run.message,
        }
    except Exception as exc:
        logger.exception("Repair task failed for %s", repair_run_id)
        failed_run = db.get(RepairRun, repair_run_id)
        if failed_run is not None:
            failed_run.status = RepairStatus.FAILED
            failed_run.message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            db.commit()
        raise exc
    finally:
        db.close()


def enqueue_repair(repair_run_id: str) -> str:
    """Queue a repair job. Returns a task id for tracking."""
    settings = get_platform_settings()
    if settings.celery_task_always_eager:
        # Eager Celery runs inline and would block webhooks until repair finishes.
        task_id = f"eager-{uuid.uuid4().hex[:12]}"

        def _run() -> None:
            try:
                run_repair.apply(args=[repair_run_id])
            except Exception:
                logger.exception("Background repair failed for %s", repair_run_id)

        threading.Thread(target=_run, daemon=True, name=f"repair-{repair_run_id[:8]}").start()
        return task_id

    result = run_repair.delay(repair_run_id)
    return str(result.id)

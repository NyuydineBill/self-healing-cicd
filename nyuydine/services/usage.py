from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nyuydine.db.models import UsageRecord


def record_usage(
    db: Session,
    *,
    organization_id: str,
    metric: str,
    quantity: int = 1,
    repair_run_id: str | None = None,
) -> UsageRecord:
    entry = UsageRecord(
        organization_id=organization_id,
        metric=metric,
        quantity=quantity,
        repair_run_id=repair_run_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_usage_total(db: Session, organization_id: str, metric: str) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.organization_id == organization_id,
            UsageRecord.metric == metric,
        )
    )
    return int(total or 0)

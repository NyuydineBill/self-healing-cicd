import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nyuydine.adapters.base import AutomationMode
from nyuydine.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RepairStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    automation_mode: Mapped[AutomationMode] = mapped_column(
        Enum(AutomationMode),
        default=AutomationMode.SUGGEST,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    repositories: Mapped[list["Repository"]] = relationship(back_populates="organization")
    repair_runs: Mapped[list["RepairRun"]] = relationship(back_populates="organization")
    usage_records: Mapped[list["UsageRecord"]] = relationship(back_populates="organization")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("github_installation_id", "full_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    github_installation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(511), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    organization: Mapped["Organization"] = relationship(back_populates="repositories")
    repair_runs: Mapped[list["RepairRun"]] = relationship(back_populates="repository")


class RepairRun(Base):
    __tablename__ = "repair_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    pipeline_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[RepairStatus] = mapped_column(
        Enum(RepairStatus), default=RepairStatus.PENDING, nullable=False
    )
    automation_mode: Mapped[AutomationMode] = mapped_column(Enum(AutomationMode), nullable=False)
    repair_success: Mapped[bool | None] = mapped_column(Boolean)
    message: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    pr_url: Mapped[str | None] = mapped_column(String(1024))
    celery_task_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="repair_runs")
    repository: Mapped["Repository"] = relationship(back_populates="repair_runs")
    attempts: Mapped[list["RepairAttemptRecord"]] = relationship(back_populates="repair_run")


class RepairAttemptRecord(Base):
    __tablename__ = "repair_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repair_run_id: Mapped[str] = mapped_column(ForeignKey("repair_runs.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(128))
    target_file: Mapped[str | None] = mapped_column(String(1024))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    repair_run: Mapped["RepairRun"] = relationship(back_populates="attempts")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    repair_run_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    organization: Mapped["Organization"] = relationship(back_populates="usage_records")

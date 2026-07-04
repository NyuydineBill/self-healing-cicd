from datetime import datetime

from pydantic import BaseModel, Field


class RepairRunSummary(BaseModel):
    id: str
    organization_id: str
    repository_id: str
    pipeline_run_id: str
    workflow_name: str | None
    status: str
    automation_mode: str
    repair_success: bool | None
    message: str | None
    pr_url: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RepairRunDetail(RepairRunSummary):
    result_json: dict | None = None
    attempts: list[dict] = Field(default_factory=list)


class TriggerRepairRequest(BaseModel):
    repository_id: str
    pipeline_run_id: str
    workflow_name: str | None = None
    automation_mode: str | None = None


class ApproveRepairRequest(BaseModel):
    approved: bool = True


class OrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    automation_mode: str


class RepositorySummary(BaseModel):
    id: str
    organization_id: str
    full_name: str
    owner: str
    name: str
    default_branch: str
    is_active: bool


class UsageSummary(BaseModel):
    organization_id: str
    repairs_total: int

"""
Append-only audit trail for all patch operations.

Every write goes to results/audit.log as a newline-delimited JSON record so
there is a persistent, human-readable history of what was changed, when, and why.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("audit_log")

_AUDIT_FILE = "audit.log"


def _audit_path() -> Path:
    return get_settings().results_dir / _AUDIT_FILE


def record_patch_applied(
    *,
    run_id: int | str,
    target_file: str,
    patch_summary: str,
    attempt: int,
    actor: str = "self-healing-bot",
    extra: dict[str, Any] | None = None,
) -> None:
    """Append a structured record when a patch is written to disk."""
    _append(
        event="patch_applied",
        run_id=run_id,
        target_file=target_file,
        patch_summary=patch_summary,
        attempt=attempt,
        actor=actor,
        **(extra or {}),
    )


def record_patch_rejected(
    *,
    run_id: int | str,
    target_file: str,
    reason: str,
    attempt: int,
    actor: str = "self-healing-bot",
) -> None:
    """Append a record when a patch fails validation or is denied approval."""
    _append(
        event="patch_rejected",
        run_id=run_id,
        target_file=target_file,
        reason=reason,
        attempt=attempt,
        actor=actor,
    )


def record_pr_opened(
    *,
    run_id: int | str,
    pr_url: str,
    branch: str,
    target_file: str,
) -> None:
    """Append a record when a repair PR is opened on GitHub."""
    _append(
        event="pr_opened",
        run_id=run_id,
        pr_url=pr_url,
        branch=branch,
        target_file=target_file,
    )


def record_run_outcome(
    *,
    run_id: int | str,
    success: bool,
    total_attempts: int,
    target_file: str | None = None,
) -> None:
    """Append a summary record at the end of each repair run."""
    _append(
        event="run_outcome",
        run_id=run_id,
        success=success,
        total_attempts=total_attempts,
        target_file=target_file,
    )


def _append(event: str, **fields: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    try:
        audit_path = _audit_path()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as exc:
        # Audit failures must never crash the main repair flow.
        logger.warning("Audit log write failed: %s", exc)

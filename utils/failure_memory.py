import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("failure_memory")


class FailureMemory:
    """Persistent JSON storage for failure history and repair outcomes."""

    def __init__(self, storage_path: Path | None = None):
        settings = get_settings()
        self.storage_path = storage_path or settings.failure_memory_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.storage_path.is_file():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load failure memory, starting fresh: %s", exc)
        return {"records": []}

    def _save(self) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

    def record_repair(
        self,
        *,
        run_id: int | str,
        failure_type: str,
        target_file: str,
        diagnosis: str,
        generated_patch: str,
        validation_outcome: dict[str, Any],
        attempt: int,
        success: bool,
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "failure_type": failure_type,
            "target_file": target_file,
            "diagnosis": diagnosis,
            "generated_patch": generated_patch,
            "validation_outcome": validation_outcome,
            "attempt": attempt,
            "success": success,
        }
        self._data["records"].append(entry)
        self._save()
        logger.info(
            "Recorded repair attempt %d for run %s (success=%s)",
            attempt,
            run_id,
            success,
        )
        return entry

    def get_repair_history(self, run_id: int | str | None = None) -> list[dict[str, Any]]:
        records = self._data.get("records", [])
        if run_id is None:
            return records
        return [r for r in records if str(r.get("run_id")) == str(run_id)]

    def get_failure_types(self) -> list[str]:
        return list(
            {r.get("failure_type") for r in self._data.get("records", []) if r.get("failure_type")}
        )

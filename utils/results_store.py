import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("results_store")


class ResultsStore:
    """Structured persistence for experimental metrics and run outcomes."""

    def __init__(self, results_dir: Optional[Path] = None):
        settings = get_settings()
        self.results_dir = results_dir or settings.results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save_run_result(self, run_id: int | str, payload: Dict[str, Any]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"run_{run_id}_{timestamp}.json"
        path = self.results_dir / filename

        record = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        logger.info("Saved run result to %s", path)
        return path

    def save_metrics(self, metrics: Dict[str, Any]) -> Path:
        path = self.results_dir / "metrics_summary.json"
        existing: Dict[str, Any] = {"runs": []}

        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        existing["runs"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **metrics,
            }
        )
        existing["total_runs"] = len(existing["runs"])
        existing["successful_repairs"] = sum(
            1 for r in existing["runs"] if r.get("repair_success")
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str)

        logger.info("Updated metrics summary at %s", path)
        return path

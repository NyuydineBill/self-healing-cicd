from collections.abc import Generator
from pathlib import Path

from config.settings import get_settings
from utils.log_extractor import iter_log_files
from utils.logging import get_logger

logger = get_logger("offline_logs")


def discover_offline_runs(logs_root: Path | None = None) -> list[tuple[str, Path]]:
    """
    Find cached workflow runs under logs/extracted/{run_id}/.

    Returns list of (run_id, extract_dir) sorted by run_id descending.
    """
    settings = get_settings()
    root = logs_root or (settings.logs_dir / "extracted")

    if not root.is_dir():
        logger.warning("Offline logs directory not found: %s", root)
        return []

    runs: list[tuple[str, Path]] = []
    for child in sorted(root.iterdir(), reverse=True):
        if child.is_dir():
            runs.append((child.name, child))

    logger.info("Discovered %d offline run(s) under %s", len(runs), root)
    return runs


def iter_offline_logs(run_id: str, extract_dir: Path) -> Generator[tuple[str, str], None, None]:
    """Yield log files for a cached run."""
    yield from iter_log_files(extract_dir)

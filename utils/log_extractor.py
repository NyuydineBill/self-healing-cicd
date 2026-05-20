import os
import zipfile
from pathlib import Path
from typing import Generator, Tuple

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("log_extractor")


def save_and_extract_logs(zip_bytes: bytes, run_id: int | str) -> Path:
    """Save workflow log ZIP and extract to logs/extracted/{run_id}/."""
    settings = get_settings()
    logs_dir = settings.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)

    zip_path = logs_dir / f"workflow_logs_{run_id}.zip"
    extract_dir = logs_dir / "extracted" / str(run_id)

    with open(zip_path, "wb") as f:
        f.write(zip_bytes)

    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    logger.info("Extracted workflow logs to %s", extract_dir)
    return extract_dir


def iter_log_files(extract_dir: Path) -> Generator[Tuple[str, str], None, None]:
    """Yield (file_path, log_text) for each extracted log file."""
    for root, _, files in os.walk(extract_dir):
        for filename in sorted(files):
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "r", errors="ignore", encoding="utf-8") as f:
                    yield file_path, f.read()
            except OSError as exc:
                logger.warning("Skipping unreadable log file %s: %s", file_path, exc)

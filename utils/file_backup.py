import shutil
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("file_backup")


class FileBackupManager:
    """Backup target files before patching and restore on failed validation."""

    def __init__(self, backup_root: Optional[Path] = None):
        settings = get_settings()
        self.backup_root = backup_root or (settings.results_dir / "backups")
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def _backup_path(self, target_file: str, run_id: int | str, label: str) -> Path:
        safe_name = Path(target_file).as_posix().replace("/", "__")
        run_dir = self.backup_root / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / f"{safe_name}.{label}.bak"

    def backup_original(self, target_file: str, run_id: int | str) -> Path:
        """Save pristine copy before any repair attempts."""
        dest = self._backup_path(target_file, run_id, "original")
        if dest.is_file():
            logger.debug("Original backup already exists: %s", dest)
            return dest

        shutil.copy2(target_file, dest)
        logger.info("Backed up original file to %s", dest)
        return dest

    def backup_before_attempt(
        self, target_file: str, run_id: int | str, attempt: int
    ) -> Path:
        """Save state immediately before applying a patch."""
        dest = self._backup_path(target_file, run_id, f"attempt{attempt}")
        shutil.copy2(target_file, dest)
        logger.debug("Pre-attempt backup: %s", dest)
        return dest

    def restore_original(self, target_file: str, run_id: int | str) -> bool:
        """Restore target file from the original backup."""
        source = self._backup_path(target_file, run_id, "original")
        if not source.is_file():
            logger.warning("No original backup to restore: %s", source)
            return False

        shutil.copy2(source, target_file)
        logger.info("Restored %s from original backup", target_file)
        return True

    def clear_run_backups(self, target_file: str, run_id: int | str) -> None:
        """Remove backup files for a completed successful repair."""
        run_dir = self.backup_root / str(run_id)
        if not run_dir.is_dir():
            return
        safe_prefix = Path(target_file).as_posix().replace("/", "__")
        for path in run_dir.glob(f"{safe_prefix}.*.bak"):
            path.unlink(missing_ok=True)
            logger.debug("Removed backup %s", path)

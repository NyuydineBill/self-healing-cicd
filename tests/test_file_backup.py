from pathlib import Path

from utils.file_backup import FileBackupManager


def test_backup_and_restore_original(tmp_backup_root, sample_target_file):
    manager = FileBackupManager(backup_root=tmp_backup_root)
    original = "def test_foo():\n    assert 1 == 2\n"

    manager.backup_original(sample_target_file, run_id=99)

    Path(sample_target_file).write_text("corrupted content", encoding="utf-8")

    assert manager.restore_original(sample_target_file, run_id=99)
    assert Path(sample_target_file).read_text(encoding="utf-8") == original


def test_clear_run_backups(tmp_backup_root, sample_target_file):
    manager = FileBackupManager(backup_root=tmp_backup_root)
    manager.backup_original(sample_target_file, run_id=1)
    manager.clear_run_backups(sample_target_file, run_id=1)

    run_dir = tmp_backup_root / "1"
    remaining = list(run_dir.glob("*.bak")) if run_dir.exists() else []
    assert len(remaining) == 0

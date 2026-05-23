from unittest.mock import MagicMock, patch

import pytest

from utils.git_repair import GitRepairManager


@pytest.fixture
def git_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123456789012345678")
    monkeypatch.setenv("GITHUB_OWNER", "owner")
    monkeypatch.setenv("GITHUB_REPO", "repo")
    monkeypatch.setenv("GIT_ENABLED", "true")

    import config.settings as settings_module

    settings_module._settings = None
    settings = settings_module.get_settings()
    object.__setattr__(settings, "project_root", tmp_path)
    return settings


def test_commit_message_includes_signed_off_by(git_settings):
    manager = GitRepairManager()
    msg = manager._commit_message(
        target_file="app/tests/test_x.py",
        run_id=99,
        failure_type="assertion_error",
        attempt=1,
    )
    assert "Signed-off-by: Self-Healing Bot" in msg
    assert "self-healing-bot@users.noreply.github.com>" in msg


def test_commit_message_omits_sign_off_when_disabled(git_settings, monkeypatch):
    monkeypatch.setenv("GIT_SIGN_OFF", "false")
    import config.settings as settings_module

    settings_module._settings = None
    manager = GitRepairManager()
    msg = manager._commit_message(
        target_file="f.py",
        run_id=1,
        failure_type="unknown",
        attempt=1,
    )
    assert "Signed-off-by:" not in msg

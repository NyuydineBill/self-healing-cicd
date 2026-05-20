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


@patch("utils.git_repair.Repo")
def test_create_pull_request(mock_repo_class, git_settings):
    manager = GitRepairManager()
    manager._repo = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"html_url": "https://github.com/o/r/pull/1"}

    with patch("utils.git_repair.requests.post", return_value=mock_response) as mock_post:
        url = manager.create_pull_request(
            branch="self-heal/run-1",
            run_id=1,
            repaired_files=["sample_projects/project_1/test.py"],
        )

    assert url == "https://github.com/o/r/pull/1"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["json"]["head"] == "self-heal/run-1"
    assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")


@patch("utils.git_repair.Repo")
def test_finalize_run_skips_pr_when_disabled(mock_repo_class, git_settings, monkeypatch):
    monkeypatch.setenv("GIT_CREATE_PR", "false")
    import config.settings as settings_module

    settings_module._settings = None

    manager = GitRepairManager()
    manager._repo = MagicMock()
    manager._active_branches["42"] = "self-heal/run-42"
    manager.push_branch = MagicMock()

    result = manager.finalize_run(42, ["file.py"])

    assert result["branch"] == "self-heal/run-42"
    assert result["pr_url"] is None
    manager.push_branch.assert_called_once()

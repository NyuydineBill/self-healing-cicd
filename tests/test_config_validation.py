import pytest

from config.settings import Settings
from config.validation import ConfigurationError, validate_configuration


def test_validate_dry_run_requires_openai_only(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(
        openai_api_key="",
        dry_run=True,
        github_token="",
        github_owner="",
        github_repo="",
    )
    with pytest.raises(ConfigurationError) as exc:
        validate_configuration(settings)
    assert "OPENAI_API_KEY" in str(exc.value)


def test_validate_live_mode_requires_github(monkeypatch, tmp_path):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "diagnosis.txt").write_text("x", encoding="utf-8")
    (prompts / "patch.txt").write_text("x", encoding="utf-8")

    settings = Settings(
        openai_api_key="sk-test",
        dry_run=False,
        github_token="",
        github_owner="owner",
        github_repo="repo",
        prompts_dir=prompts,
    )
    with pytest.raises(ConfigurationError) as exc:
        validate_configuration(settings)
    assert "GITHUB_TOKEN" in str(exc.value)

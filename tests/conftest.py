import pytest


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings singleton between tests."""
    import config.settings as settings_module

    settings_module._settings = None
    yield
    settings_module._settings = None


@pytest.fixture
def tmp_backup_root(tmp_path):
    return tmp_path / "backups"


@pytest.fixture
def sample_target_file(tmp_path):
    target = tmp_path / "sample_projects" / "project_1" / "test_example.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_foo():\n    assert 1 == 2\n", encoding="utf-8")
    return str(target)


@pytest.fixture
def prompts_dir(tmp_path, monkeypatch):
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "diagnosis.txt").write_text(
        "Context: {failure_context}\nType: {failure_type}", encoding="utf-8"
    )
    (prompt_dir / "patch.txt").write_text(
        "Fix: {failure_context}\n{diagnosis}\n{target_file}",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DRY_RUN", "true")
    import config.settings as settings_module

    settings_module._settings = None
    settings = settings_module.get_settings()
    object.__setattr__(settings, "prompts_dir", prompt_dir)
    return prompt_dir

from config.check import run_health_check
from config.settings import Settings


def test_offline_cache_optional_when_not_offline_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DRY_RUN", "true")

    import config.settings as settings_module

    settings_module._settings = None
    settings = Settings(
        project_root=tmp_path,
        prompts_dir=tmp_path / "prompts",
        results_dir=tmp_path / "results",
        logs_dir=tmp_path / "logs",
        offline_mode=False,
        dry_run=True,
    )
    settings.prompts_dir.mkdir(parents=True)
    (settings.prompts_dir / "diagnosis.txt").write_text("x", encoding="utf-8")
    (settings.prompts_dir / "patch.txt").write_text("x", encoding="utf-8")

    assert run_health_check(settings) == 0


def test_offline_cache_required_when_offline_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OFFLINE_MODE", "true")

    import config.settings as settings_module

    settings_module._settings = None
    settings = Settings(
        project_root=tmp_path,
        prompts_dir=tmp_path / "prompts",
        results_dir=tmp_path / "results",
        logs_dir=tmp_path / "logs",
        offline_mode=True,
        dry_run=True,
    )
    settings.prompts_dir.mkdir(parents=True)
    (settings.prompts_dir / "diagnosis.txt").write_text("x", encoding="utf-8")
    (settings.prompts_dir / "patch.txt").write_text("x", encoding="utf-8")

    assert run_health_check(settings) == 1

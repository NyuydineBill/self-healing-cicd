from utils.offline_logs import discover_offline_runs


def test_discover_offline_runs_empty(tmp_path, monkeypatch):
    import config.settings as settings_module

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings_module._settings = None
    settings = settings_module.get_settings()
    object.__setattr__(settings, "logs_dir", tmp_path)

    assert discover_offline_runs() == []


def test_discover_offline_runs_finds_cached(tmp_path, monkeypatch):
    import config.settings as settings_module

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings_module._settings = None
    settings = settings_module.get_settings()
    object.__setattr__(settings, "logs_dir", tmp_path)

    (tmp_path / "extracted" / "12345").mkdir(parents=True)
    (tmp_path / "extracted" / "12345" / "job.log").write_text("FAILED", encoding="utf-8")

    runs = discover_offline_runs()
    assert len(runs) == 1
    assert runs[0][0] == "12345"

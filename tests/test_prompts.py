import pytest

from utils.prompts import load_prompt


def test_load_prompt_substitutes_variables(prompts_dir):
    import config.settings as settings_module

    settings = settings_module.get_settings()
    result = load_prompt(
        "diagnosis",
        {"failure_context": "FAILED test", "failure_type": "assertion_error"},
    )
    assert "FAILED test" in result
    assert "assertion_error" in result


def test_load_prompt_missing_template_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent", {})


def test_load_prompt_missing_variable_raises(prompts_dir):
    with pytest.raises(KeyError):
        load_prompt("diagnosis", {"failure_context": "only one var"})

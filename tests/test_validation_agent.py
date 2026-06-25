import sys

from agents.validation_agent import ValidationAgent


def test_normalize_replay_strips_cov_flags_and_uses_local_python():
    agent = ValidationAgent()
    cmd = (
        "/opt/hostedtoolcache/Python/3.12.13/x64/bin/python -m pytest "
        "tests/ sample_projects/ -v --cov=. --cov-report=term-missing --cov-report=xml"
    )
    parts = agent._normalize_replay_parts(__import__("shlex").split(cmd))

    assert parts[0] == sys.executable
    assert "-o" in parts
    assert parts[parts.index("-o") + 1] == "addopts="
    assert "--cov=." not in parts
    assert not any(p.startswith("--cov-report") for p in parts)


def test_validate_patch_scopes_sample_project_repairs():
    agent = ValidationAgent()
    result = agent.validate_patch(
        target_file="sample_projects/project_1/test_unit_failure.py",
        failing_command="pytest tests/ sample_projects/ -v --cov=.",
    )
    assert result["status"] in ("success", "failed")
    assert result.get("scope") == "sample_projects/project_1"


def test_replay_clears_pytest_ini_addopts():
    agent = ValidationAgent()
    cmd = "pytest tests/ sample_projects/ -v --cov=. --cov-report=term-missing --cov-report=xml"
    parts = agent._normalize_replay_parts(__import__("shlex").split(cmd))
    env = agent._pytest_env()
    assert env.get("PYTEST_ADDOPTS") == ""
    assert "-o" in parts
    assert parts[parts.index("-o") + 1] == "addopts="
    assert "--cov=." not in parts

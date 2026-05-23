import pytest

from utils.policy import PolicyViolation, enforce_path_policy, is_path_allowed


def test_allowed_sample_project_path():
    assert is_path_allowed("sample_projects/project_1/test_foo.py")


def test_rejects_outside_prefix():
    assert not is_path_allowed("etc/passwd")
    assert not is_path_allowed("random/outside/module.py")


def test_enforce_raises():
    with pytest.raises(PolicyViolation):
        enforce_path_policy("/etc/passwd")

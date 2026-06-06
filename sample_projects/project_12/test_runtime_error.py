import pytest

from sample_projects.project_12.app import safe_divide


def test_divide_normal():
    assert safe_divide(10, 2) == 5.0


def test_divide_by_zero_raises():
    with pytest.raises(RuntimeError):
        safe_divide(5, 0)

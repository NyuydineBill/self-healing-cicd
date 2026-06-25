from pathlib import Path

from utils.assertion_repair import deterministic_assertion_test_fix


def test_fixes_wrong_expected_value_from_pytest_summary(tmp_path, monkeypatch):
    target = "sample_projects/project_1/test_unit_failure.py"
    failure_context = (
        "AssertionError\n"
        "FAILED sample_projects/project_1/test_unit_failure.py::test_add - assert 4 == 999\n"
    )
    monkeypatch.chdir(tmp_path)
    path = Path(target)
    path.parent.mkdir(parents=True)
    path.write_text(
        "from sample_projects.project_1.app import add\n\n\n"
        "def test_add():\n"
        "    assert add(2, 2) == 999\n",
        encoding="utf-8",
    )

    fixed = deterministic_assertion_test_fix(target, failure_context)
    assert fixed is not None
    assert "== 4" in fixed
    assert "== 999" not in fixed


def test_returns_none_for_non_test_file():
    assert (
        deterministic_assertion_test_fix(
            "sample_projects/project_1/app.py",
            "E   assert 4 == 999",
        )
        is None
    )

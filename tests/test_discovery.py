from utils.discovery import discover_all_test_targets, discover_tests_under_prefixes


def test_discover_tests_under_app_prefix():
    paths = discover_tests_under_prefixes(["app/"])
    assert any("app/tests/test_calculator.py" in p for p in paths)


def test_discover_all_includes_sample_and_app():
    paths = discover_all_test_targets()
    assert any("sample_projects" in p for p in paths)
    assert any("app/tests" in p for p in paths)

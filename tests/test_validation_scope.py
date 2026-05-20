from utils.validation_scope import resolve_validation_scope


def test_resolve_scope_from_test_file():
    scope = resolve_validation_scope(
        "sample_projects/project_2/test_import_error.py"
    )
    assert scope == "sample_projects/project_2"


def test_resolve_scope_from_nested_path():
    scope = resolve_validation_scope(
        "/app/sample_projects/project_3/test_syntax_error.py"
    )
    assert scope == "sample_projects/project_3"


def test_resolve_scope_returns_none_for_unrelated_file():
    assert resolve_validation_scope("src/main.py") is None

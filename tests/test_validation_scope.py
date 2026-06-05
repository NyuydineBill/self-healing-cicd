from utils.validation_scope import resolve_validation_scope


def test_resolve_scope_from_test_file():
    scope = resolve_validation_scope("sample_projects/project_2/test_import_error.py")
    assert scope == "sample_projects/project_2"


def test_resolve_scope_from_nested_path():
    scope = resolve_validation_scope("/app/sample_projects/project_3/test_syntax_error.py")
    assert scope == "sample_projects/project_3"


def test_resolve_scope_for_app_tests():
    scope = resolve_validation_scope("app/tests/test_calculator.py")
    assert scope == "app"


def test_resolve_scope_for_src_tree():
    scope = resolve_validation_scope("src/mypkg/test_foo.py")
    assert scope == "src/mypkg" or scope == "src"

from utils.errors import ErrorCategory, categorize_failure


def test_categorize_import_error():
    assert categorize_failure(["ImportError: cannot import name 'add'"]) == ErrorCategory.IMPORT


def test_categorize_assertion_error():
    assert categorize_failure(["AssertionError: assert 1 == 2"]) == ErrorCategory.ASSERTION


def test_categorize_syntax_error():
    assert categorize_failure(["SyntaxError: invalid syntax"]) == ErrorCategory.SYNTAX


def test_categorize_build_from_validation_status():
    assert categorize_failure([], validation_status="build_failed") == ErrorCategory.BUILD


def test_categorize_unknown():
    assert categorize_failure(["something odd happened"]) == ErrorCategory.UNKNOWN

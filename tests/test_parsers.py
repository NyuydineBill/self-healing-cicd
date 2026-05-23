from parsers import get_parser
from parsers.go_parser import GoLogParser
from parsers.java_parser import JavaLogParser
from parsers.python_parser import PythonLogParser


def test_python_parser_extracts_sample_project_file():
    log = 'File "/app/sample_projects/project_1/test_foo.py", line 10\nAssertionError: fail'
    parser = PythonLogParser()
    assert parser.extract_failed_file(log) == "sample_projects/project_1/test_foo.py"
    assert parser.extract_failure_context(log)


def test_java_parser_matches_maven_error():
    log = "[ERROR] src/main/java/app/Service.java:[42,1] error: ';' expected"
    parser = JavaLogParser()
    assert parser.matches(log)
    path = parser.extract_failed_file(log)
    assert path and path.endswith(".java")


def test_go_parser_matches_test_failure():
    log = "--- FAIL: TestAdd (app/pkg/math_test.go:12)"
    parser = GoLogParser()
    assert parser.matches(log)
    assert "math_test.go" in (parser.extract_failed_file(log) or "")


def test_get_parser_auto_detects_java():
    log = "BUILD FAILURE\n[ERROR] src/app/Main.java:[1,1]"
    parser = get_parser(log)
    assert parser.language == "java"

import re
from enum import StrEnum


class ErrorCategory(StrEnum):
    ASSERTION = "assertion_error"
    IMPORT = "import_error"
    SYNTAX = "syntax_error"
    MODULE_NOT_FOUND = "module_not_found"
    DEPENDENCY = "dependency_error"
    BUILD = "build_error"
    RUNTIME = "runtime_error"
    UNKNOWN = "unknown"


_PATTERNS: list[tuple[ErrorCategory, re.Pattern]] = [
    (ErrorCategory.ASSERTION, re.compile(r"AssertionError|FAILED", re.I)),
    (ErrorCategory.IMPORT, re.compile(r"ImportError|cannot import name", re.I)),
    (ErrorCategory.MODULE_NOT_FOUND, re.compile(r"ModuleNotFoundError", re.I)),
    (ErrorCategory.SYNTAX, re.compile(r"SyntaxError", re.I)),
    (ErrorCategory.DEPENDENCY, re.compile(r"No matching distribution found", re.I)),
    (ErrorCategory.BUILD, re.compile(r"build_failed|docker build", re.I)),
    (ErrorCategory.RUNTIME, re.compile(r"Error:", re.I)),
]


def categorize_failure(errors: list[str], validation_status: str | None = None) -> ErrorCategory:
    """Classify failure context into a structured error category."""
    if validation_status == "build_failed":
        return ErrorCategory.BUILD

    combined = "\n".join(errors)
    for category, pattern in _PATTERNS:
        if pattern.search(combined):
            return category

    return ErrorCategory.UNKNOWN

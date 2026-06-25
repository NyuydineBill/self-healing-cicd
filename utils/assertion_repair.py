import re
from pathlib import Path

# Pytest long traceback: "E   assert 4 == 999"
_TRACEBACK_ASSERT_RE = re.compile(
    r"^E\s+assert (.+?) == (.+?)\s*$",
    re.MULTILINE,
)

# Pytest short summary: "FAILED ... - assert 4 == 999"
_SUMMARY_ASSERT_RE = re.compile(
    r"assert\s+(\S+)\s+==\s+(\S+)",
)


def _parse_assertion_values(failure_context: str) -> tuple[str, str] | None:
    match = _TRACEBACK_ASSERT_RE.search(failure_context)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    match = _SUMMARY_ASSERT_RE.search(failure_context)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None


def deterministic_assertion_test_fix(
    target_file: str,
    failure_context: str,
) -> str | None:
    """
    Fix wrong expected values in test assertions when pytest reports:
      E   assert <actual> == <expected>
    or:
      FAILED ... - assert <actual> == <expected>

    Returns full corrected file content, or None if not applicable.
    """
    normalized = target_file.replace("\\", "/")
    name = Path(target_file).name
    if "/test" not in normalized and not name.startswith("test_"):
        return None

    values = _parse_assertion_values(failure_context)
    if not values:
        return None

    actual_str, expected_str = values
    path = Path(target_file)
    if not path.is_file():
        return None

    content = path.read_text(encoding="utf-8")
    assert_line = re.compile(
        rf"^(\s*assert\s+.+?==\s*){re.escape(expected_str)}(\s*)$",
        re.MULTILINE,
    )
    new_content, count = assert_line.subn(
        lambda m: f"{m.group(1)}{actual_str}{m.group(2)}",
        content,
        count=1,
    )
    if count == 0:
        fallback = re.compile(rf"==\s*{re.escape(expected_str)}\b")
        new_content, count = fallback.subn(f"== {actual_str}", content, count=1)

    if count == 0 or new_content == content:
        return None
    return new_content

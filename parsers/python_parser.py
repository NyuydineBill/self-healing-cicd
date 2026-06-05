import re

from parsers.base import LogParser


class PythonLogParser(LogParser):
    language = "python"

    ERROR_PATTERNS = [
        r"AssertionError.*",
        r"FAILED.*",
        r"ImportError.*",
        r"cannot import name.*",
        r"ModuleNotFoundError.*",
        r"SyntaxError.*",
        r"No matching distribution found.*",
        r"Error:.*",
    ]

    FILE_PATTERNS = [
        r'File ".*?(sample_projects/.*?\.py)"',
        r'File ".*?(app/.*?\.py)"',
        r'File ".*?(src/.*?\.py)"',
        r'File ".*?(tests/.*?\.py)"',
        r'File ".*?(lib/.*?\.py)"',
    ]

    def matches(self, log_text: str) -> bool:
        hints = (
            "pytest",
            "AssertionError",
            "ImportError",
            "SyntaxError",
            "ModuleNotFoundError",
            "sample_projects/",
            ".py",
        )
        return any(h in log_text for h in hints)

    def extract_failure_context(self, log_text: str) -> list[str]:
        extracted: list[str] = []
        for pattern in self.ERROR_PATTERNS:
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            if matches:
                extracted.extend(matches)
        return extracted

    def extract_failed_file(self, log_text: str) -> str | None:
        for pattern in self.FILE_PATTERNS:
            match = re.search(pattern, log_text)
            if match:
                return match.group(1)
        return None

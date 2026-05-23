import re
from typing import List, Optional

from parsers.base import LogParser


class JavaLogParser(LogParser):
    language = "java"

    ERROR_PATTERNS = [
        r"\[ERROR\].*",
        r"BUILD FAILURE.*",
        r"Failed to execute goal.*",
        r"Tests run:.*Failures: [1-9].*",
        r"java\.lang\.\w+Error:.*",
        r"java\.lang\.\w+Exception:.*",
        r"AssertionError:.*",
        r"COMPILATION ERROR.*",
    ]

    FILE_PATTERNS = [
        r"\[ERROR\]\s+(.+?\.java):\[(\d+)",
        r"at .+?\((.+?\.java):\d+\)",
        r"(\S+\.java):\[\d+,\d+\]",
    ]

    def matches(self, log_text: str) -> bool:
        hints = ("[ERROR]", "BUILD FAILURE", "mvn ", "gradle", ".java", "surefire")
        return any(h in log_text for h in hints)

    def extract_failure_context(self, log_text: str) -> List[str]:
        extracted: List[str] = []
        for pattern in self.ERROR_PATTERNS:
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            if matches:
                extracted.extend(matches)
        return extracted

    def extract_failed_file(self, log_text: str) -> Optional[str]:
        for pattern in self.FILE_PATTERNS:
            for match in re.finditer(pattern, log_text):
                path = match.group(1)
                if path.endswith(".java") and not path.startswith("http"):
                    return self._normalize_path(path)
        return None

    @staticmethod
    def _normalize_path(path: str) -> str:
        path = path.strip().replace("\\", "/")
        for prefix in ("src/", "app/", "lib/"):
            idx = path.find(prefix)
            if idx >= 0:
                return path[idx:]
        return path

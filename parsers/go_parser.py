import re
from typing import List, Optional

from parsers.base import LogParser


class GoLogParser(LogParser):
    language = "go"

    ERROR_PATTERNS = [
        r"FAIL\s+.*",
        r"--- FAIL:.*",
        r"panic:.*",
        r"Error:\s+.*",
        r"build failed.*",
        r"cannot find package.*",
        r"undefined:.*",
        r"FAIL\t.*",
    ]

    def matches(self, log_text: str) -> bool:
        hints = ("--- FAIL:", "FAIL\t", "panic:", ".go:", "go test", "go build")
        return any(h in log_text for h in hints)

    def extract_failure_context(self, log_text: str) -> List[str]:
        extracted: List[str] = []
        for pattern in self.ERROR_PATTERNS:
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            if matches:
                extracted.extend(matches)
        return extracted

    def extract_failed_file(self, log_text: str) -> Optional[str]:
        patterns = [
            r"--- FAIL:\s+\S+\s+\((.+?\.go):\d+\)",
            r"(\S+\.go):(\d+):",
            r"FAIL\s+.*?\((.+?\.go)",
        ]
        for pattern in patterns:
            match = re.search(pattern, log_text)
            if match:
                path = match.group(1).replace("\\", "/")
                for prefix in ("src/", "app/", "lib/", "cmd/", "internal/"):
                    idx = path.find(prefix)
                    if idx >= 0:
                        return path[idx:]
                if path.endswith(".go"):
                    return path
        return None

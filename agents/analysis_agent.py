import re
from typing import List, Optional

from utils.logging import get_logger

logger = get_logger("analysis_agent")


class AnalysisAgent:

    def extract_failure_context(self, log_text: str) -> List[str]:
        patterns = [
            r"AssertionError.*",
            r"FAILED.*",
            r"ImportError.*",
            r"cannot import name.*",
            r"ModuleNotFoundError.*",
            r"SyntaxError.*",
            r"No matching distribution found.*",
            r"Error:.*",
        ]

        extracted_errors = []

        for pattern in patterns:
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            if matches:
                extracted_errors.extend(matches)

        if extracted_errors:
            logger.debug("Extracted %d error line(s) from log", len(extracted_errors))

        return extracted_errors

    def extract_failed_file(self, log_text: str) -> Optional[str]:
        match = re.search(
            r'File ".*?(sample_projects/.*?\.py)"',
            log_text,
        )

        if match:
            return match.group(1)

        return None

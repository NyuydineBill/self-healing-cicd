from typing import List, Optional

from parsers import get_parser
from utils.logging import get_logger

logger = get_logger("analysis_agent")


class AnalysisAgent:

    def extract_failure_context(self, log_text: str) -> List[str]:
        parser = get_parser(log_text)
        logger.debug("Using log parser: %s", parser.language)
        errors = parser.extract_failure_context(log_text)
        if errors:
            logger.debug(
                "Extracted %d error line(s) via %s parser",
                len(errors),
                parser.language,
            )
        return errors

    def extract_failed_file(self, log_text: str) -> Optional[str]:
        parser = get_parser(log_text)
        return parser.extract_failed_file(log_text)

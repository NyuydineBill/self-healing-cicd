import re


class AnalysisAgent:

    def extract_failure_context(self, log_text):

        patterns = [
            r"AssertionError.*",
            r"FAILED.*",
            r"ImportError.*",
            r"cannot import name.*",
            r"ModuleNotFoundError.*",
            r"SyntaxError.*",
            r"No matching distribution found.*",
            r"Error:.*"
        ]

        extracted_errors = []

        for pattern in patterns:

            matches = re.findall(
                pattern,
                log_text,
                re.IGNORECASE
            )

            if matches:
                extracted_errors.extend(matches)

        return extracted_errors
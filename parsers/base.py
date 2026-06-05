from abc import ABC, abstractmethod


class LogParser(ABC):
    """Pluggable log parser for multi-language CI failures."""

    language: str = "unknown"

    @abstractmethod
    def extract_failure_context(self, log_text: str) -> list[str]:
        """Extract error lines from workflow log text."""

    @abstractmethod
    def extract_failed_file(self, log_text: str) -> str | None:
        """Resolve a repository-relative path to the failing file, if possible."""

    def matches(self, log_text: str) -> bool:
        """Return True if this parser is likely appropriate for the log."""
        return False

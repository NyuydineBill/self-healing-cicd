import os
from typing import List, Optional, Type

from parsers.base import LogParser
from parsers.go_parser import GoLogParser
from parsers.java_parser import JavaLogParser
from parsers.python_parser import PythonLogParser

_PARSERS: List[Type[LogParser]] = [
    PythonLogParser,
    JavaLogParser,
    GoLogParser,
]

_LANGUAGE_OVERRIDE = os.getenv("LOG_PARSER_LANGUAGE", "").strip().lower()


def get_parser(log_text: str) -> LogParser:
    """Select the best parser for log content, or use LOG_PARSER_LANGUAGE override."""
    if _LANGUAGE_OVERRIDE:
        for cls in _PARSERS:
            if cls.language == _LANGUAGE_OVERRIDE:
                return cls()
        raise ValueError(f"Unknown LOG_PARSER_LANGUAGE: {_LANGUAGE_OVERRIDE}")

    for cls in _PARSERS:
        instance = cls()
        if instance.matches(log_text):
            return instance

    return PythonLogParser()


def list_parsers() -> List[str]:
    return [cls.language for cls in _PARSERS]

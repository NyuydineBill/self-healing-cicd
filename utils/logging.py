import logging
import sys
from typing import Optional

from config.settings import get_settings
from utils.secrets import mask_secrets, register_secrets

_CONFIGURED = False


class SecretsRedactionFilter(logging.Filter):
    """Mask secrets in log records before they are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        if record.args:
            record.args = tuple(
                mask_secrets(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def setup_logging(level: Optional[str] = None) -> None:
    """Configure structured logging with secret redaction."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    register_secrets([
        settings.github_token,
        settings.openai_api_key,
    ])

    log_level = getattr(
        logging, (level or settings.log_level).upper(), logging.INFO
    )

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SecretsRedactionFilter())

    root = logging.getLogger("self_healing")
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"self_healing.{name}")

import logging
import sys
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import get_settings
from utils.secrets import mask_secrets, register_secrets

_CONFIGURED = False

# Per-async-task (or per-thread) correlation ID — set at orchestrator entry.
_run_id_var: ContextVar[str] = ContextVar("run_id", default="")


def set_run_id(run_id: str | int) -> None:
    """Bind a run_id to the current execution context for log correlation."""
    _run_id_var.set(str(run_id))


def get_run_id() -> str:
    return _run_id_var.get()


class _ContextFilter(logging.Filter):
    """Inject run_id and mask secrets in every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id_var.get() or "-"
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        if record.args:
            record.args = tuple(
                mask_secrets(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


def setup_logging(level: str | None = None) -> None:
    """Configure structured logging with secret redaction and log rotation."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    register_secrets(
        [
            settings.github_token,
            settings.openai_api_key,
        ]
    )

    log_level = getattr(logging, (level or settings.log_level).upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(run_id)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ctx_filter = _ContextFilter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ctx_filter)

    handlers: list[logging.Handler] = [console_handler]

    # Rotating file handler — 5 MB per file, keep 5 backups
    log_file = Path(settings.logs_dir) / "self_healing.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ctx_filter)
        handlers.append(file_handler)
    except OSError:
        # Non-fatal: log directory may not be writable in CI
        pass

    root = logging.getLogger("self_healing")
    root.setLevel(log_level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"self_healing.{name}")

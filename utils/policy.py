from pathlib import Path

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("policy")


class PolicyViolation(Exception):
    """Raised when a repair target violates path policy."""


def get_allowed_prefixes() -> list[str]:
    settings = get_settings()
    return list(settings.allowed_path_prefixes)


def is_path_allowed(target_file: str, prefixes: list[str] | None = None) -> bool:
    """Return True if target_file is under an allowed prefix."""
    prefixes = prefixes if prefixes is not None else get_allowed_prefixes()
    if not prefixes:
        return True

    normalized = Path(target_file).as_posix().lstrip("./")
    for prefix in prefixes:
        clean = prefix.strip().rstrip("/")
        if normalized == clean or normalized.startswith(f"{clean}/"):
            return True
    return False


def enforce_path_policy(target_file: str) -> None:
    """Raise PolicyViolation if the target file is not allowed."""
    if not is_path_allowed(target_file):
        allowed = ", ".join(get_allowed_prefixes())
        raise PolicyViolation(f"Target file '{target_file}' is outside allowed paths: {allowed}")
    logger.debug("Path policy OK for %s", target_file)

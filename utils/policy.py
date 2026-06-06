import contextlib
from pathlib import Path

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger("policy")

_SKIP_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".tox",
    "dist",
    "build",
    ".eggs",
    ".mypy_cache",
    ".ruff_cache",
}


class PolicyViolation(Exception):
    """Raised when a repair target violates path policy."""


def auto_discover_prefixes(root: Path | None = None) -> list[str]:
    """
    Scan the working directory for top-level directories that contain Python
    (or JS/TS/Go) source files and return them as allowed path prefixes.
    Falls back to ["."] if only root-level files are found.
    """
    cwd = root or Path.cwd()
    top_dirs: set[str] = set()
    has_root_files = False

    for src_file in cwd.glob("**/*"):
        if not src_file.is_file():
            continue
        if src_file.suffix not in {".py", ".js", ".ts", ".go", ".rs"}:
            continue
        try:
            rel = src_file.relative_to(cwd)
        except ValueError:
            continue
        parts = rel.parts
        # Skip hidden / build / venv directories
        if any(p.startswith(".") or p in _SKIP_DIRS or p.endswith(".egg-info") for p in parts[:-1]):
            continue
        if len(parts) == 1:
            has_root_files = True
        else:
            top_dirs.add(parts[0] + "/")

    prefixes = sorted(top_dirs)
    if not prefixes and has_root_files:
        prefixes = ["."]
    logger.info("Auto-discovered path prefixes: %s", prefixes)
    return prefixes or ["."]


def get_allowed_prefixes() -> list[str]:
    settings = get_settings()
    explicit = list(settings.allowed_path_prefixes)
    # "auto" sentinel or empty list triggers discovery
    if not explicit or explicit == ["auto"]:
        return auto_discover_prefixes()
    return explicit


def is_path_allowed(target_file: str, prefixes: list[str] | None = None) -> bool:
    """Return True if target_file is under an allowed prefix."""
    prefixes = prefixes if prefixes is not None else get_allowed_prefixes()
    if not prefixes:
        return True

    p = Path(target_file)
    # Normalize absolute paths to CWD-relative so prefix checks work correctly
    if p.is_absolute():
        with contextlib.suppress(ValueError):
            p = p.relative_to(Path.cwd())
    normalized = p.as_posix().lstrip("./")
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

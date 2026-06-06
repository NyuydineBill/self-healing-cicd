import os
from pathlib import Path

from config.settings import get_settings
from utils.logging import get_logger
from utils.policy import _SKIP_DIRS, get_allowed_prefixes

logger = get_logger("discovery")


def discover_sample_tests(base_dir: str = "sample_projects") -> list[str]:
    """Discover test_*.py files under sample project directories."""
    sample_tests: list[str] = []

    if not os.path.isdir(base_dir):
        return sample_tests

    for project_name in sorted(os.listdir(base_dir)):
        project_dir = os.path.join(base_dir, project_name)
        if not os.path.isdir(project_dir):
            continue

        for root, _, files in os.walk(project_dir):
            for filename in sorted(files):
                if filename.startswith("test_") and filename.endswith(".py"):
                    sample_tests.append(os.path.join(root, filename))

    return sample_tests


def discover_tests_under_prefixes(prefixes: list[str] | None = None) -> list[str]:
    """
    Discover test files under configured allowed path prefixes.
    Uses auto_discover_prefixes() when no explicit prefixes are configured.
    """
    prefixes = prefixes or get_allowed_prefixes()
    discovered: list[str] = []

    logger.info("discover_tests_under_prefixes: cwd=%s prefixes=%s", Path.cwd(), prefixes)
    for prefix in prefixes:
        base = Path(prefix.rstrip("/"))
        if not base.is_dir():
            logger.info("Prefix dir not found: %s (resolved: %s)", base, base.resolve())
            continue

        for root, dirs, files in os.walk(base):
            # Prune skip directories in-place so os.walk doesn't descend into them
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in _SKIP_DIRS and not d.endswith(".egg-info")
            ]
            for filename in sorted(files):
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("test_") or "test" in root.replace("\\", "/").split("/"):
                    discovered.append(str(Path(root) / filename))

    return sorted(set(discovered))


def discover_source_files(prefixes: list[str] | None = None) -> list[str]:
    """
    Discover all Python source files under allowed prefixes.
    Used as a fallback when no dedicated test files exist.
    """
    prefixes = prefixes or get_allowed_prefixes()
    discovered: list[str] = []

    for prefix in prefixes:
        base = Path(prefix.rstrip("/"))
        if not base.is_dir():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in _SKIP_DIRS and not d.endswith(".egg-info")
            ]
            for filename in sorted(files):
                if filename.endswith(".py"):
                    discovered.append(str(Path(root) / filename))

    return sorted(set(discovered))


def discover_all_test_targets() -> list[str]:
    """
    Merge sample-project tests, prefix-scoped test files, and — when no tests
    exist — all source files so the orchestrator always has something to target.
    """
    settings = get_settings()
    paths = discover_sample_tests(settings.sample_projects_dir)
    paths.extend(discover_tests_under_prefixes())

    if not paths:
        logger.info("No test files found; falling back to all source files for repair targeting")
        paths.extend(discover_source_files())

    return sorted(set(paths))

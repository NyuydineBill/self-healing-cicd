import os
from pathlib import Path
from typing import List

from config.settings import get_settings


def discover_sample_tests(base_dir: str = "sample_projects") -> List[str]:
    """Discover test_*.py files under sample project directories."""
    sample_tests: List[str] = []

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


def discover_tests_under_prefixes(prefixes: List[str] | None = None) -> List[str]:
    """
    Discover test files under configured allowed path prefixes.

    Supports pytest-style test_*.py and tests/ directories.
    """
    settings = get_settings()
    prefixes = prefixes or list(settings.allowed_path_prefixes)
    discovered: List[str] = []

    for prefix in prefixes:
        base = Path(prefix.rstrip("/"))
        if not base.is_dir():
            continue

        for root, _, files in os.walk(base):
            for filename in sorted(files):
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("test_") or "/tests/" in root.replace("\\", "/"):
                    discovered.append(str(Path(root) / filename))

    return sorted(set(discovered))


def discover_all_test_targets() -> List[str]:
    """Merge sample projects and broader app/src test discovery."""
    settings = get_settings()
    paths = discover_sample_tests(settings.sample_projects_dir)
    paths.extend(discover_tests_under_prefixes())
    return sorted(set(paths))

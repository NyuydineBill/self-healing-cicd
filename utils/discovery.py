import os
from typing import List


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

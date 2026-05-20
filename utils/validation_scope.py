from pathlib import Path
from typing import Optional


def resolve_validation_scope(
    target_file: str,
    sample_projects_dir: str = "sample_projects",
) -> Optional[str]:
    """
    Derive a scoped pytest path from a target file under sample_projects.

    Example: sample_projects/project_1/test_foo.py -> sample_projects/project_1
    """
    path = Path(target_file)
    parts = path.parts

    for i, part in enumerate(parts):
        if part == sample_projects_dir and i + 1 < len(parts):
            project = parts[i + 1]
            if project.startswith("project_"):
                return str(Path(sample_projects_dir) / project)

    for part in parts:
        if part.startswith("project_"):
            return str(Path(sample_projects_dir) / part)

    return None

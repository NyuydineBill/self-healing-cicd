from pathlib import Path
from typing import Optional


def resolve_validation_scope(
    target_file: str,
    sample_projects_dir: str = "sample_projects",
) -> Optional[str]:
    """
    Derive a scoped pytest path from a target file.

    Examples:
      sample_projects/project_1/test_foo.py -> sample_projects/project_1
      app/tests/test_calc.py -> app
      src/mypkg/test_x.py -> src/mypkg or src
    """
    path = Path(target_file)
    parts = path.parts

    for i, part in enumerate(parts):
        if part == sample_projects_dir and i + 1 < len(parts):
            project = parts[i + 1]
            if project.startswith("project_"):
                return str(Path(sample_projects_dir) / project)

    if "tests" in parts:
        idx = parts.index("tests")
        if idx > 0:
            return str(Path(*parts[:idx]))

    for prefix in ("app", "src", "lib"):
        if prefix in parts:
            idx = parts.index(prefix)
            return str(Path(*parts[: idx + 1]))

    parent = path.parent
    if parent.parts:
        return str(parent)

    return None

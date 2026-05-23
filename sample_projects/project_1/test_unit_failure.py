from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo — remove or revert after testing
    assert add(2, 2) == 999
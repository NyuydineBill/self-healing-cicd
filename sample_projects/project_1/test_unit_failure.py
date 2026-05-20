from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo — revert before final merge
    assert add(2, 2) == 999

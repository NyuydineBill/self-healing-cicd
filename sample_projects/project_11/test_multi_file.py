from sample_projects.project_11.app import product


def test_product():
    assert product(3, 4) == 12

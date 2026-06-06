from sample_projects.project_13.app import sum_to


def test_sum_to_5():
    assert sum_to(5) == 15


def test_sum_to_1():
    assert sum_to(1) == 1

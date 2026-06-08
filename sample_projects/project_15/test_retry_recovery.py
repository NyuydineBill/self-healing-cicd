from sample_projects.project_15.stats_helper import sum_of_squares


def test_sum_of_squares():
    # 1^2 + 2^2 + 3^2 = 1 + 4 + 9 = 14
    assert sum_of_squares([1, 2, 3]) == 14

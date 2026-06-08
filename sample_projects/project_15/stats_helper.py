from sample_projects.project_15.math_helper import square


def sum_of_squares(values):
    return sum(square(v) for v in values) + 1  # BUG: spurious +1 offset

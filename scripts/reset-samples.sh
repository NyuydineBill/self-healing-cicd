#!/usr/bin/env bash
# Restore all sample_projects to passing (golden) state.
set -euo pipefail
cd "$(dirname "$0")/.."

write() {
  local path="$1"
  shift
  mkdir -p "$(dirname "$path")"
  cat > "$path" <<EOF
$@
EOF
}

# project_1
write sample_projects/project_1/test_unit_failure.py 'from sample_projects.project_1.app import add


def test_add():
    assert add(2, 2) == 4'

write sample_projects/project_1/app.py 'def add(a, b):
    return a + b'

# project_2
write sample_projects/project_2/test_import_error.py 'from sample_projects.project_2.app import add


def test_add():
    assert add(2, 2) == 4'

write sample_projects/project_2/app.py 'def add(a, b):
    return a + b'

# project_3
write sample_projects/project_3/test_syntax_error.py 'from sample_projects.project_3.app import add


def test_add():
    assert add(2, 2) == 4'

write sample_projects/project_3/app.py 'def add(a, b):
    return a + b'

# project_4
write sample_projects/project_4/app.py 'def add(a, b):
    return a + b'

write sample_projects/project_4/test_logic_bug.py 'from sample_projects.project_4.app import add


def test_add():
    assert add(2, 2) == 4'

# project_5
write sample_projects/project_5/test_module_not_found.py 'from sample_projects.project_5.app import add


def test_add():
    assert add(1, 1) == 2'

write sample_projects/project_5/app.py 'def add(a, b):
    return a + b'

# project_6
write sample_projects/project_6/test_attribute_error.py 'from sample_projects.project_6.app import add


def test_add():
    assert add(3, 4) == 7'

write sample_projects/project_6/app.py 'def add(a, b):
    return a + b'

# project_7
write sample_projects/project_7/app.py 'def add(a, b):
    return a + b'

write sample_projects/project_7/test_name_error.py 'from sample_projects.project_7.app import add


def test_add():
    assert add(5, 5) == 10'

# project_8
write sample_projects/project_8/app.py 'def first(items):
    return items[0]'

write sample_projects/project_8/test_index_error.py 'from sample_projects.project_8.app import first


def test_first_returns_head():
    assert first([10, 20, 30]) == 10'

# project_9
write sample_projects/project_9/app.py 'def add(a, b):
    return a + b'

write sample_projects/project_9/test_type_error.py 'from sample_projects.project_9.app import add


def test_add_integers():
    assert add(2, 3) == 5'

# project_10
write sample_projects/project_10/app.py 'def divide(a, b):
    return a / b'

write sample_projects/project_10/test_zero_division.py 'from sample_projects.project_10.app import divide


def test_divide():
    assert divide(10, 2) == 5'

# project_11
write sample_projects/project_11/app.py 'def product(a, b):
    return a * b'

write sample_projects/project_11/test_multi_file.py 'from sample_projects.project_11.app import product


def test_product():
    assert product(3, 4) == 12'

# project_12
write sample_projects/project_12/app.py 'def safe_divide(a, b):
    if b == 0:
        raise ValueError("divisor cannot be zero")
    return a / b'

write sample_projects/project_12/test_runtime_error.py 'import pytest

from sample_projects.project_12.app import safe_divide


def test_divide_normal():
    assert safe_divide(10, 2) == 5.0


def test_divide_by_zero_raises():
    with pytest.raises(ValueError):
        safe_divide(5, 0)'

# project_13
write sample_projects/project_13/app.py 'def sum_to(n):
    """Return the sum of integers from 1 to n inclusive."""
    total = 0
    for i in range(1, n + 1):
        total += i
    return total'

write sample_projects/project_13/test_off_by_one.py 'from sample_projects.project_13.app import sum_to


def test_sum_to_5():
    assert sum_to(5) == 15


def test_sum_to_1():
    assert sum_to(1) == 1'

# project_14
write sample_projects/project_14/app.py 'def greet(name, count):
    """Return a greeting repeated `count` times."""
    return ("Hello, " + str(name) + "! ") * count'

write sample_projects/project_14/test_type_error.py 'from sample_projects.project_14.app import greet


def test_greet_once():
    assert greet("Alice", 1) == "Hello, Alice! "


def test_greet_twice():
    result = greet("Bob", 2)
    assert result == "Hello, Bob! Hello, Bob! "


def test_greet_with_number_name():
    assert greet(42, 1) == "Hello, 42! "'

# project_15
write sample_projects/project_15/math_helper.py 'def square(x):
    return x * x'

write sample_projects/project_15/stats_helper.py 'from sample_projects.project_15.math_helper import square


def sum_of_squares(values):
    return sum(square(v) for v in values)'

write sample_projects/project_15/test_retry_recovery.py 'from sample_projects.project_15.stats_helper import sum_of_squares


def test_sum_of_squares():
    assert sum_of_squares([1, 2, 3]) == 14'

echo "All sample_projects restored to golden (passing) state."

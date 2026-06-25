#!/usr/bin/env bash
# Introduce a known failure in sample_projects/project_N for CI / self-heal demos.
# Usage: ./scripts/break-sample.sh [1-15]
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${1:-1}"
if ! [[ "$PROJECT" =~ ^([1-9]|1[0-5])$ ]]; then
  echo "Usage: $0 <project_number 1-15>" >&2
  exit 1
fi

# Ensure golden state for other projects (optional: only break target)
"$(dirname "$0")/reset-samples.sh" >/dev/null

case "$PROJECT" in
  1)
    cat > sample_projects/project_1/test_unit_failure.py <<'EOF'
from sample_projects.project_1.app import add


def test_add():
    # Intentional failure for self-heal demo
    assert add(2, 2) == 999
EOF
    ;;
  2)
    cat > sample_projects/project_2/test_import_error.py <<'EOF'
from sample_projects.project_2.app import multiply


def test_add():
    assert multiply(2, 2) == 4
EOF
    ;;
  3)
    cat > sample_projects/project_3/app.py <<'EOF'
def add(a, b)
    return a + b
EOF
    ;;
  4)
    cat > sample_projects/project_4/app.py <<'EOF'
def add(a, b):
    return a - b
EOF
    ;;
  5)
    cat > sample_projects/project_5/test_module_not_found.py <<'EOF'
from sample_projects.project_5.missing_module import helper


def test_add():
    assert helper(1, 1) == 2
EOF
    ;;
  6)
    cat > sample_projects/project_6/test_attribute_error.py <<'EOF'
import sample_projects.project_6.app as mod


def test_add():
    assert mod.add_numbers(3, 4) == 7
EOF
    ;;
  7)
    cat > sample_projects/project_7/app.py <<'EOF'
def add(a, b):
    return a + b + offset
EOF
    ;;
  8)
    cat > sample_projects/project_8/app.py <<'EOF'
def first(items):
    return items[99]
EOF
    ;;
  9)
    cat > sample_projects/project_9/app.py <<'EOF'
def add(a, b):
    return str(a) + str(b)
EOF
    ;;
  10)
    cat > sample_projects/project_10/app.py <<'EOF'
def divide(a, b):
    return a / 0
EOF
    ;;
  11)
    cat > sample_projects/project_11/app.py <<'EOF'
def multiply(a, b):
    return a * b
EOF
    cat > sample_projects/project_11/test_multi_file.py <<'EOF'
from sample_projects.project_11.app import product


def test_product():
    assert product(3, 4) == 12
EOF
    ;;
  12)
    cat > sample_projects/project_12/test_runtime_error.py <<'EOF'
import pytest

from sample_projects.project_12.app import safe_divide


def test_divide_normal():
    assert safe_divide(10, 2) == 5.0


def test_divide_by_zero_raises():
    with pytest.raises(RuntimeError):
        safe_divide(5, 0)
EOF
    ;;
  13)
    cat > sample_projects/project_13/app.py <<'EOF'
def sum_to(n):
    """Return the sum of integers from 1 to n inclusive."""
    total = 0
    for i in range(1, n):
        total += i
    return total
EOF
    ;;
  14)
    cat > sample_projects/project_14/app.py <<'EOF'
def greet(name, count):
    """Return a greeting repeated `count` times."""
    return ("Hello, " + name + "! ") * count
EOF
    ;;
  15)
    cat > sample_projects/project_15/math_helper.py <<'EOF'
def square(x):
    return x * x * x  # BUG: computes cube, not square
EOF
    cat > sample_projects/project_15/stats_helper.py <<'EOF'
from sample_projects.project_15.math_helper import square


def sum_of_squares(values):
    return sum(square(v) for v in values) + 1  # BUG: spurious +1 offset
EOF
    ;;
esac

echo "Broke sample_projects/project_${PROJECT} — run: pytest sample_projects/project_${PROJECT}/ -v"
echo "Then: git add sample_projects/ && git commit -m 'test: intentional CI failure in project_${PROJECT}' && git push"

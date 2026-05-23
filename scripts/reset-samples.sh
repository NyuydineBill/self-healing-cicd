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

echo "All sample_projects restored to golden (passing) state."

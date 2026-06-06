from sample_projects.project_14.app import greet


def test_greet_once():
    assert greet("Alice", 1) == "Hello, Alice! "


def test_greet_twice():
    result = greet("Bob", 2)
    assert result == "Hello, Bob! Hello, Bob! "


def test_greet_with_number_name():
    assert greet(42, 1) == "Hello, 42! "

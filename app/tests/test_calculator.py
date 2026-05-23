from app.calculator import add, subtract


def test_add():
    assert add(2, 2) == 4
    assert add(999, 0) == 999


def test_subtract():
    assert subtract(5, 3) == 2
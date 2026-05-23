from app.calculator import add, subtract


def test_add():
    assert add(2, 2) == 4


def test_subtract():
    assert subtract(5, 3) == 2

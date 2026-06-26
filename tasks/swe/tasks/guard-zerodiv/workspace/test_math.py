from mathutils import safe_divide


def test_normal():
    assert safe_divide(6, 2) == 3
    assert safe_divide(9, 3) == 3


def test_zero_returns_none():
    assert safe_divide(1, 0) is None

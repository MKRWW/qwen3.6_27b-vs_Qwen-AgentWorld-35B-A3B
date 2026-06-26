import pytest
from geometry.shapes import circle_area, rectangle_area


def test_circle_area():
    assert circle_area(2) == pytest.approx(12.566, rel=1e-3)
    assert circle_area(1) == pytest.approx(3.14159, rel=1e-3)


def test_rectangle_area():
    assert rectangle_area(3, 4) == 12

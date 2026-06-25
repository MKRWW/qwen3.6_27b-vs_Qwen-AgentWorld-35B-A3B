from utils import sum_range


def test_small():
    assert sum_range(1) == 1
    assert sum_range(3) == 6      # 1+2+3
    assert sum_range(5) == 15     # 1+2+3+4+5


def test_zero():
    assert sum_range(0) == 0

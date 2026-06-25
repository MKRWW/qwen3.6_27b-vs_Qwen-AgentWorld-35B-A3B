def sum_range(n):
    """Summe der ganzen Zahlen von 1 bis n (inklusive).

    BUG: range(1, n) schliesst n aus -> Ergebnis um n zu klein.
    """
    total = 0
    for i in range(1, n):  # off-by-one
        total += i
    return total

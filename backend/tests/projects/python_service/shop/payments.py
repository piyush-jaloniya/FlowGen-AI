from .repository import unit_price


def calculate_total(quantity):
    if quantity < 0:
        raise ValueError("quantity must be nonnegative")
    return quantity * unit_price()

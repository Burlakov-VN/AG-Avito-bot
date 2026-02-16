"""Generate Price field with rules applied."""

import math


def calculate_price(raw_price: float, rules: dict) -> int:
    """Apply price rules (markup, rounding, min/max) and return final price.

    Rules keys:
        markup_percent: percentage to add (e.g. 10 = +10%)
        round_to: round to nearest N (e.g. 10)
        min_price: minimum allowed price
        max_price: maximum allowed price (null = no cap)
    """
    markup = rules.get("markup_percent", 0)
    price = raw_price * (1 + markup / 100)

    round_to = rules.get("round_to", 1)
    if round_to > 1:
        price = math.ceil(price / round_to) * round_to

    price = int(price)

    min_price = rules.get("min_price", 0)
    if price < min_price:
        price = min_price

    max_price = rules.get("max_price")
    if max_price is not None and price > max_price:
        price = max_price

    return price

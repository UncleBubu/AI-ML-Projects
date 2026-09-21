"""Money helpers. Paystack speaks integer kobo; our DB speaks naira numeric(12,2).

Decimal (not float) everywhere money is computed: 19.99 * 100 is 1998.9999999999998 as a float.
ALL conversions go through these two functions.
"""
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def naira_to_kobo(naira: Decimal | str | float) -> int:
    return int((Decimal(str(naira)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kobo_to_naira(kobo: int) -> Decimal:
    return (Decimal(kobo) / 100).quantize(TWO_PLACES)

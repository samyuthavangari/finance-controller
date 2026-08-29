from decimal import Decimal, ROUND_HALF_EVEN

TWOPLACES = Decimal("0.01")


def money(value) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    else:
        d = Decimal(str(value))
    return d.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal("0")
    return (part / whole * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

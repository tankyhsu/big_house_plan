from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _round_financial(value: float, precision: int = 8) -> float:
    """Round financial values with consistent precision using Decimal."""
    if value == 0.0:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP))


def round_price(value: float) -> float:
    """Round price values to 4 decimal places."""
    return _round_financial(value, 4)


def round_quantity(value: float) -> float:
    """Round quantity values to 2 decimal places."""
    return _round_financial(value, 2)


def round_shares(value: float) -> float:
    """Round share quantities to 2 decimal places (legacy: was 8)."""
    return _round_financial(value, 2)


def round_amount(value: float) -> float:
    """Round monetary amounts to 4 decimal places."""
    return _round_financial(value, 4)


def compute_position_after_trade(
    old_shares: float,
    old_avg_cost: float,
    action: str,
    qty: float,
    price: float | None,
    fee: float,
) -> tuple[float, float]:
    """
    Given current position and an incoming txn, compute new (shares, avg_cost).
    - BUY adds shares; avg_cost is recalculated with fee capitalized.
    - SELL reduces shares; avg_cost kept unless shares goes to zero.
    - DIV/FEE/ADJ do not change position for the instrument itself.

    Returns (new_shares, new_avg_cost).
    """
    action_u = (action or "").upper()
    qty_abs = abs(float(qty or 0.0))
    p = float(price or 0.0)
    f = float(fee or 0.0)

    if action_u == "BUY":
        new_shares = round_shares(old_shares + qty_abs)
        total_cost = round_amount(old_shares * old_avg_cost + qty_abs * p + f)
        new_cost = round_price((total_cost / new_shares) if new_shares > 0 else 0.0)
        return new_shares, new_cost
    elif action_u == "SELL":
        new_shares = round_shares(old_shares - qty_abs)
        new_cost = old_avg_cost if new_shares > 0.01 else 0.0  # 调整阈值
        return new_shares, new_cost
    else:
        # DIV / FEE / ADJ: no change to instrument position
        return old_shares, old_avg_cost


def compute_cash_mirror(
    action: str,
    qty: float,
    price: float | None,
    fee: float,
    amount: float | None,
) -> tuple[str | None, float]:
    """
    Compute the mirrored cash txn for a non-cash instrument txn.
    Returns (mirror_action, mirror_abs_amount). If no mirror, returns (None, 0.0).

    Rules:
    - BUY:   cash SELL, amount = gross + fee
    - SELL:  cash BUY,  amount = gross - fee
    - DIV:   cash BUY,  amount = amount
    - FEE:   cash SELL, amount = fee or amount
    - ADJ:   amount>0 => cash BUY, amount<0 => cash SELL
    """
    action_u = (action or "").upper()
    qty_abs = abs(float(qty or 0.0))
    p = float(price or 0.0)
    f = float(fee or 0.0)
    amt_field = None if amount is None else float(amount)
    gross = float(amt_field) if amt_field is not None else (qty_abs * p)

    if action_u == "BUY":
        return "SELL", round_amount(max(0.0, gross + f))
    if action_u == "SELL":
        return "BUY", round_amount(max(0.0, gross - f))
    if action_u == "DIV":
        return "BUY", round_amount(max(0.0, gross))
    if action_u == "FEE":
        return "SELL", round_amount(max(0.0, (f if f else gross)))
    if action_u == "ADJ":
        a = float(amt_field or 0.0)
        if a > 0:
            return "BUY", round_amount(a)
        if a < 0:
            return "SELL", round_amount(-a)
    return None, 0.0


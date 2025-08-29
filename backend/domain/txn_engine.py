from typing import Optional, Tuple


def compute_position_after_trade(
    old_shares: float,
    old_avg_cost: float,
    action: str,
    qty: float,
    price: Optional[float],
    fee: float,
) -> Tuple[float, float]:
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
        new_shares = old_shares + qty_abs
        total_cost = old_shares * old_avg_cost + qty_abs * p + f
        new_cost = (total_cost / new_shares) if new_shares > 0 else 0.0
        return new_shares, new_cost
    elif action_u == "SELL":
        new_shares = round(old_shares - qty_abs, 8)
        new_cost = old_avg_cost if new_shares > 0 else 0.0
        return new_shares, new_cost
    else:
        # DIV / FEE / ADJ: no change to instrument position
        return old_shares, old_avg_cost


def compute_cash_mirror(
    action: str,
    qty: float,
    price: Optional[float],
    fee: float,
    amount: Optional[float],
) -> Tuple[Optional[str], float]:
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
        return "SELL", max(0.0, gross + f)
    if action_u == "SELL":
        return "BUY", max(0.0, gross - f)
    if action_u == "DIV":
        return "BUY", max(0.0, gross)
    if action_u == "FEE":
        return "SELL", max(0.0, (f if f else gross))
    if action_u == "ADJ":
        a = float(amt_field or 0.0)
        if a > 0:
            return "BUY", a
        if a < 0:
            return "SELL", -a
    return None, 0.0


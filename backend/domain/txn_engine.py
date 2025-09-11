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
) -> tuple[float, float, float]:
    """
    Enhanced position calculation with proper cost basis tracking.
    
    Returns (new_shares, new_avg_cost, realized_pnl)
    
    Key improvements:
    - BUY: Weighted average cost with proper fee capitalization  
    - SELL: Calculate realized P&L and maintain accurate cost basis
    - DIV: Handle cash dividends (no position change)
    - STOCK_DIV: Handle stock dividends (adjust shares and cost)
    - SPLIT: Handle stock splits (adjust shares and cost proportionally)
    """
    action_u = (action or "").upper()
    qty_abs = abs(float(qty or 0.0))
    p = float(price or 0.0)
    f = float(fee or 0.0)
    realized_pnl = 0.0

    if action_u == "BUY":
        # Add shares with weighted average cost calculation
        new_shares = round_shares(old_shares + qty_abs)
        if new_shares > 0:
            total_old_cost = old_shares * old_avg_cost
            total_new_cost = qty_abs * p + f  # Fee capitalized into cost basis
            new_avg_cost = round_price((total_old_cost + total_new_cost) / new_shares)
        else:
            new_avg_cost = 0.0
        return new_shares, new_avg_cost, realized_pnl

    elif action_u == "SELL":
        # Calculate realized P&L and update position
        if old_shares > 0 and qty_abs > 0:
            # Realized P&L = (sell_price - avg_cost) * shares_sold - fees
            realized_pnl = round_amount((p - old_avg_cost) * qty_abs - f)
        
        new_shares = round_shares(old_shares - qty_abs)
        # Keep same average cost unless position is completely closed (near zero)
        # For negative positions (overselling), maintain the original cost
        new_avg_cost = old_avg_cost if abs(new_shares) > 0.01 else 0.0
        return new_shares, new_avg_cost, realized_pnl

    elif action_u == "DIV":
        # Cash dividend - no position change, dividend recorded elsewhere
        return old_shares, old_avg_cost, realized_pnl

    elif action_u == "STOCK_DIV":
        # Stock dividend - increase shares, reduce average cost proportionally
        # qty represents dividend ratio (e.g., 0.1 for 10% stock dividend)
        dividend_shares = round_shares(old_shares * qty_abs)
        new_shares = round_shares(old_shares + dividend_shares)
        # Cost basis stays same, spread over more shares
        new_avg_cost = round_price(old_avg_cost * old_shares / new_shares) if new_shares > 0 else 0.0
        return new_shares, new_avg_cost, realized_pnl

    elif action_u == "SPLIT":
        # Stock split - adjust shares and cost proportionally  
        # qty represents split ratio (e.g., 2.0 for 2:1 split)
        new_shares = round_shares(old_shares * qty_abs)
        new_avg_cost = round_price(old_avg_cost / qty_abs) if qty_abs > 0 else old_avg_cost
        return new_shares, new_avg_cost, realized_pnl

    elif action_u == "FEE":
        # Management fee or other costs - reduce cost basis
        if old_shares > 0:
            new_avg_cost = round_price(old_avg_cost + f / old_shares)
        else:
            new_avg_cost = old_avg_cost
        return old_shares, new_avg_cost, -f  # Fee is negative realized P&L

    else:
        # Unknown action - no change
        return old_shares, old_avg_cost, realized_pnl


def compute_position_with_corporate_actions(
    old_shares: float,
    old_avg_cost: float,
    transactions: list[dict],
) -> tuple[float, float, float]:
    """
    Process multiple transactions in chronological order to get final position.
    
    Args:
        old_shares: Starting share count
        old_avg_cost: Starting average cost  
        transactions: List of transaction dicts with keys:
            - action: Transaction type (BUY/SELL/DIV/STOCK_DIV/SPLIT/FEE)
            - qty: Quantity 
            - price: Price per share
            - fee: Transaction fee
    
    Returns:
        (final_shares, final_avg_cost, total_realized_pnl)
    """
    current_shares = old_shares
    current_avg_cost = old_avg_cost
    total_realized_pnl = 0.0
    
    for txn in transactions:
        new_shares, new_avg_cost, realized_pnl = compute_position_after_trade(
            current_shares,
            current_avg_cost, 
            txn.get("action"),
            txn.get("qty", 0),
            txn.get("price", 0),
            txn.get("fee", 0)
        )
        current_shares = new_shares
        current_avg_cost = new_avg_cost
        total_realized_pnl = round_amount(total_realized_pnl + realized_pnl)
    
    return current_shares, current_avg_cost, total_realized_pnl


def calculate_cost_basis_adjustment(
    shares: float,
    avg_cost: float,
    adjustment_type: str,
    adjustment_value: float
) -> tuple[float, float]:
    """
    Handle cost basis adjustments for special corporate actions.
    
    Args:
        shares: Current share count
        avg_cost: Current average cost
        adjustment_type: Type of adjustment (SPINOFF/MERGER/RIGHTS/etc)
        adjustment_value: Value of the adjustment
    
    Returns:
        (adjusted_shares, adjusted_avg_cost)
    """
    if adjustment_type == "SPINOFF":
        # Spinoff - allocate cost basis between parent and spun-off entity
        # adjustment_value represents the percentage allocated to spinoff
        spinoff_ratio = min(max(adjustment_value, 0.0), 1.0)
        new_avg_cost = round_price(avg_cost * (1.0 - spinoff_ratio))
        return shares, new_avg_cost
    
    elif adjustment_type == "MERGER":
        # Merger - typically converts to cash or other securities
        # adjustment_value is the conversion ratio
        return 0.0, 0.0
    
    elif adjustment_type == "RIGHTS":
        # Rights offering - may adjust cost basis if rights are exercised
        # This would need more complex logic based on rights terms
        return shares, avg_cost
    
    else:
        # Unknown adjustment type - no change
        return shares, avg_cost


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


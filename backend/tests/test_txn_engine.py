from backend.domain.txn_engine import compute_position_after_trade, compute_cash_mirror


def test_buy_recalculates_avg_cost():
    ns, nc = compute_position_after_trade(0.0, 0.0, "BUY", 100, 10.0, 1.0)
    assert abs(ns - 100.0) < 1e-8
    assert abs(nc - 10.01) < 1e-8


def test_sell_reduces_shares_keeps_cost_until_zero():
    ns, nc = compute_position_after_trade(100.0, 10.01, "SELL", 40, 10.5, 2.0)
    assert abs(ns - 60.0) < 1e-8
    assert abs(nc - 10.01) < 1e-8


def test_sell_over_position_engine_may_go_negative():
    # Engine is pure math; guard is enforced in service layer
    ns, nc = compute_position_after_trade(10.0, 5.0, "SELL", 20, 6.0, 0.0)
    assert ns < 0
    assert abs(nc - 5.0) < 1e-8 or nc == 0.0


def test_cash_mirror_buy_and_sell():
    act, amt = compute_cash_mirror("BUY", 100, 10.0, 1.0, None)
    assert act == "SELL" and abs(amt - 1001.0) < 1e-8
    act2, amt2 = compute_cash_mirror("SELL", 100, 10.0, 1.0, None)
    assert act2 == "BUY" and abs(amt2 - 999.0) < 1e-8


def test_cash_mirror_div_fee_adj():
    act, amt = compute_cash_mirror("DIV", 0, None, 0.0, 123.45)
    assert act == "BUY" and abs(amt - 123.45) < 1e-8
    act2, amt2 = compute_cash_mirror("FEE", 0, None, 7.0, None)
    assert act2 == "SELL" and abs(amt2 - 7.0) < 1e-8
    act3, amt3 = compute_cash_mirror("ADJ", 0, None, 0.0, -50)
    assert act3 == "SELL" and abs(amt3 - 50.0) < 1e-8


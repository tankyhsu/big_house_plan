from __future__ import annotations

from backend.db import get_conn


def test_sell_realized_pnl_and_cash_mirror(client):
    # 1) BUY 100 @10, fee=2 -> avg_cost = 10.02
    res1 = client.post(
        "/api/txn/create",
        json={
            "ts_code": "600000.SH",
            "date": "2025-08-30",
            "action": "BUY",
            "shares": 100,
            "price": 10.0,
            "fee": 2.0,
        },
    )
    assert res1.status_code == 201

    # 2) SELL 60 @11, fee=1 -> realized = 60*(11-10.02)-1 = 57.8
    res2 = client.post(
        "/api/txn/create",
        json={
            "ts_code": "600000.SH",
            "date": "2025-08-30",
            "action": "SELL",
            "shares": 60,
            "price": 11.0,
            "fee": 1.0,
        },
    )
    assert res2.status_code == 201

    # Check list API: realized_pnl present on SELL row
    lst = client.get("/api/txn/list", params={"page": 1, "size": 50}).json()
    items = lst["items"]
    # Find the SELL row for 600000.SH
    sell_rows = [r for r in items if r["ts_code"] == "600000.SH" and r["action"] == "SELL"]
    assert sell_rows, f"no SELL rows found: {items}"
    rp = float(sell_rows[0]["realized_pnl"])
    assert abs(rp - 57.8) < 1e-6

    # Positions reflect 40 remaining @ 10.02
    with get_conn() as conn:
        pos = conn.execute(
            "SELECT shares, avg_cost FROM position WHERE ts_code=?",
            ("600000.SH",),
        ).fetchone()
        assert pos is not None
        assert abs(pos["shares"] - 40.0) < 1e-8
        assert abs(pos["avg_cost"] - 10.02) < 1e-8

        # Mirror for SELL: CASH buy amount = gross-fee = 60*11-1 = 659
        rows = conn.execute(
            "SELECT ts_code, action, shares, price FROM txn WHERE ts_code='CASH.CNY' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        assert rows is not None
        assert rows["action"] == "BUY"
        assert abs(rows["shares"] - 659.0) < 1e-8
        assert abs(rows["price"] - 1.0) < 1e-8


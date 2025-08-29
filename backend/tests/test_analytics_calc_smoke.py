from backend.db import get_conn


def ensure_basic_mapping():
    with get_conn() as conn:
        # Ensure category exists
        row = conn.execute(
            "SELECT id FROM category WHERE name=? AND sub_name=?",
            ("测试分类", "子类"),
        ).fetchone()
        if row:
            cat_id = int(row["id"])
        else:
            cur1 = conn.execute(
                "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
                ("测试分类", "子类", 0.0),
            )
            cat_id = int(cur1.lastrowid)
        # Instruments
        conn.execute(
            "INSERT OR REPLACE INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,?)",
            ("600000.SH", "浦发银行", "STOCK", cat_id, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,?)",
            ("CASH.CNY", "现金", "CASH", cat_id, 1),
        )
        conn.commit()


def test_analytics_and_calc_end_to_end(client):
    ensure_basic_mapping()

    # Create two txns (BUY then SELL) same day
    r1 = client.post(
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
    assert r1.status_code == 201

    r2 = client.post(
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
    assert r2.status_code == 201

    # Insert price for terminal value in XIRR and for calc snapshot
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO price_eod(ts_code, trade_date, close) VALUES(?,?,?)",
            ("600000.SH", "2025-08-30", 11.0),
        )
        conn.commit()

    # Single IRR
    irr = client.get("/api/position/irr", params={"ts_code": "600000.SH", "date": "20250830"}).json()
    assert irr["annualized_mwr"] is None or isinstance(irr["annualized_mwr"], float)
    assert irr["flows"] >= 2

    # Batch IRR should include skip_cash for CASH.CNY
    irr_batch = client.get("/api/position/irr/batch", params={"date": "20250830"}).json()
    cash = next((x for x in irr_batch if x["ts_code"] == "CASH.CNY"), None)
    assert cash is not None
    assert cash.get("irr_reason") == "skip_cash"

    # Calc snapshot and check dashboard numbers
    calc = client.post("/api/calc", json={"date": "20250830"}).json()
    assert calc["message"] == "ok"

    dash = client.get("/api/dashboard", params={"date": "20250830"}).json()
    kpi = dash["kpi"]
    assert kpi["market_value"] >= 0 and kpi["cost"] >= 0

    # Position view should reflect remaining 40 shares and market value 40*11
    pos = client.get("/api/position", params={"date": "20250830"}).json()
    row = next((r for r in pos if r["ts_code"] == "600000.SH"), None)
    assert row is not None
    assert abs(row["shares"] - 40.0) < 1e-8
    assert abs(row["market_value"] - 40.0 * 11.0) < 1e-6

    # Price endpoint
    lp = client.get("/api/price/last", params={"ts_code": "600000.SH", "date": "20250830"}).json()
    assert lp["close"] == 11.0 and lp["trade_date"] == "2025-08-30"

from backend.db import get_conn


def test_health_and_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    v = client.get("/version")
    assert v.status_code == 200
    assert v.json().get("app") == "portfolio-ui-api"


def test_txn_create_with_cash_mirror(client):
    # Create a simple BUY txn
    payload = {
        "ts_code": "000001.SZ",
        "date": "2025-08-29",
        "action": "BUY",
        "shares": 100,
        "price": 10.0,
        "fee": 1.0,
    }
    res = client.post("/api/txn/create", json=payload)
    assert res.status_code == 201
    assert res.json().get("message") == "ok"

    # Validate DB side-effects: 2 txn rows linked by group_id, positions updated
    with get_conn() as conn:
        rows = conn.execute("SELECT rowid as id, ts_code, action, shares, price, fee, group_id FROM txn ORDER BY rowid").fetchall()
        assert len(rows) == 2
        ids = [r["id"] for r in rows]
        groups = {r["group_id"] for r in rows}
        assert len(groups) == 1 and list(groups)[0] == ids[0]  # group_id == original id

        # Original instrument BUY
        orig = rows[0]
        assert orig["ts_code"] == "000001.SZ" and orig["action"] == "BUY"
        # Cash mirror SELL, amount = 100*10 + 1 = 1001 (as negative shares)
        mirror = rows[1]
        assert mirror["ts_code"] == "CASH.CNY" and mirror["action"] == "SELL"
        assert abs(mirror["shares"] + 1001.0) < 1e-6
        assert mirror["price"] == 1.0

        # Positions
        p1 = conn.execute("SELECT shares, avg_cost FROM position WHERE ts_code=?", ("000001.SZ",)).fetchone()
        assert p1 is not None
        # avg_cost = (100*10 + 1)/100 = 10.01
        assert abs(p1["shares"] - 100.0) < 1e-8
        assert abs(p1["avg_cost"] - 10.01) < 1e-8

        pc = conn.execute("SELECT shares, avg_cost FROM position WHERE ts_code=?", ("CASH.CNY",)).fetchone()
        assert pc is not None
        assert abs(pc["shares"] + 1001.0) < 1e-8  # negative cash allowed


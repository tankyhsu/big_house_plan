def test_calc_endpoint_runs(client):
    # Without any data it should still succeed
    r = client.post("/api/calc", json={"date": "20250830"})
    assert r.status_code == 200
    assert r.json().get("message") == "ok"


def test_sync_prices_no_token(client):
    # No token configured by default in tests; endpoint should not error
    r = client.post("/api/sync-prices", json={"date": "20250830", "recalc": False})
    assert r.status_code == 200
    data = r.json()
    assert data.get("reason") == "no_token"

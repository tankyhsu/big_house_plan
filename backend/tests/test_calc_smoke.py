def test_calc_endpoint_runs(client):
    # Without any data it should still succeed
    r = client.post("/api/calc", json={"date": "20250830"})
    assert r.status_code == 200
    assert r.json().get("message") == "ok"


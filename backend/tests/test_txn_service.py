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

        # Mirror for SELL: CASH ADJ (unified type for cash mirror), amount = gross-fee = 60*11-1 = 659
        rows = conn.execute(
            "SELECT ts_code, action, shares, price FROM txn WHERE ts_code='CASH.CNY' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        assert rows is not None
        assert rows["action"] == "ADJ"
        assert abs(rows["shares"] - 659.0) < 1e-8
        assert abs(rows["price"] - 1.0) < 1e-8

def test_t_operation_detection_and_grouping(client):
    """测试T+0操作检测和自动分组功能"""
    ts_code = "000001.SZ"
    trade_date = "2024-01-15"
    
    # 测试用例1：标准T操作 - 先买入后卖出相同数量
    # 1) 买入100股@10元
    res1 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "BUY",
            "shares": 100,
            "price": 10.0,
            "fee": 5.0,
        },
    )
    assert res1.status_code == 201
    buy_result = res1.json()
    assert not buy_result["position"].get("t_trade_detected", False)  # 第一笔不应检测到T操作
    
    # 2) 卖出100股@12元 (应该检测到T操作)
    res2 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "SELL",
            "shares": 100,
            "price": 12.0,
            "fee": 5.0,
        },
    )
    assert res2.status_code == 201
    sell_result = res2.json()
    assert sell_result["position"].get("t_trade_detected", False)  # 应该检测到T操作
    
    # 3) 验证数据库中的分组
    with get_conn() as conn:
        # 查询这两笔交易的group_id
        rows = conn.execute("""
            SELECT id, action, shares, group_id 
            FROM txn 
            WHERE ts_code = ? AND trade_date = ? AND action IN ('BUY', 'SELL')
            ORDER BY id
        """, (ts_code, trade_date)).fetchall()
        
        assert len(rows) == 2, f"Expected 2 transactions, got {len(rows)}"
        
        buy_row = next((r for r in rows if r[1] == 'BUY'), None)
        sell_row = next((r for r in rows if r[1] == 'SELL'), None)
        
        assert buy_row is not None, "BUY transaction not found"
        assert sell_row is not None, "SELL transaction not found"
        assert buy_row[3] == sell_row[3], f"Group IDs don't match: BUY={buy_row[3]}, SELL={sell_row[3]}"
        assert buy_row[3] is not None, "Group ID should not be None"


def test_t_operation_no_match_different_quantity(client):
    """测试T操作检测 - 不同数量不应匹配"""
    ts_code = "000002.SZ"
    trade_date = "2024-01-16"
    
    # 1) 买入100股@10元
    res1 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "BUY",
            "shares": 100,
            "price": 10.0,
            "fee": 5.0,
        },
    )
    assert res1.status_code == 201
    
    # 2) 卖出200股@12元 (数量不匹配，不应该检测到T操作)
    res2 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "SELL",
            "shares": 200,
            "price": 12.0,
            "fee": 5.0,
        },
    )
    assert res2.status_code == 201
    sell_result = res2.json()
    assert not sell_result["position"].get("t_trade_detected", False)  # 不应检测到T操作
    
    # 3) 验证分组 - 应该使用各自的ID作为group_id
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, action, group_id 
            FROM txn 
            WHERE ts_code = ? AND trade_date = ? AND action IN ('BUY', 'SELL')
            ORDER BY id
        """, (ts_code, trade_date)).fetchall()
        
        assert len(rows) == 2
        buy_row, sell_row = rows[0], rows[1]
        
        # 应该各自使用自己的ID作为group_id（非T操作）
        assert buy_row[2] == buy_row[0], f"BUY group_id should equal its ID: {buy_row[2]} != {buy_row[0]}"
        assert sell_row[2] == sell_row[0], f"SELL group_id should equal its ID: {sell_row[2]} != {sell_row[0]}"


def test_t_operation_reverse_order(client):
    """测试T操作检测 - 先卖后买也应该检测到"""
    ts_code = "000003.SZ"
    trade_date = "2024-01-17"
    
    # 先建立初始持仓
    client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": "2024-01-10",
            "action": "BUY",
            "shares": 500,
            "price": 9.0,
            "fee": 10.0,
        },
    )
    
    # 1) 先卖出150股@11元
    res1 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "SELL",
            "shares": 150,
            "price": 11.0,
            "fee": 5.0,
        },
    )
    assert res1.status_code == 201
    
    # 2) 再买入150股@10元 (应该检测到T操作)
    res2 = client.post(
        "/api/txn/create",
        json={
            "ts_code": ts_code,
            "date": trade_date,
            "action": "BUY",
            "shares": 150,
            "price": 10.0,
            "fee": 5.0,
        },
    )
    assert res2.status_code == 201
    buy_result = res2.json()
    assert buy_result["position"].get("t_trade_detected", False)  # 应该检测到T操作
    
    # 3) 验证T操作分组
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, action, group_id 
            FROM txn 
            WHERE ts_code = ? AND trade_date = ? AND action IN ('BUY', 'SELL')
            ORDER BY id
        """, (ts_code, trade_date)).fetchall()
        
        assert len(rows) == 2
        sell_row, buy_row = rows[0], rows[1]
        
        assert sell_row[2] == buy_row[2], f"Group IDs should match: SELL={sell_row[2]}, BUY={buy_row[2]}"


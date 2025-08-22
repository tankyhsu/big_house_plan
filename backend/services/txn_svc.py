from ..db import get_conn
from ..logs import LogContext
from typing import List, Tuple

def list_txn(page:int, size:int) -> Tuple[int, List[dict]]:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(1) AS c FROM txn").fetchone()["c"]
        rows = conn.execute("""
            SELECT rowid as id, ts_code, trade_date, action, shares, price, amount, fee, notes
            FROM txn ORDER BY trade_date DESC, rowid DESC LIMIT ? OFFSET ?
        """, (size, (page-1)*size)).fetchall()
        return total, [dict(r) for r in rows]

def create_txn(data: dict, log: LogContext) -> dict:
    action = data["action"].upper()
    shares = float(data["shares"])
    fee = float(data.get("fee") or 0)
    price = float(data.get("price") or 0)
    date = data["date"]  # YYYY-MM-DD
    if action == "SELL":
        shares = -abs(shares)
    elif action in ("BUY","DIV","FEE","ADJ"):
        shares = abs(shares)
    else:
        raise ValueError("Unsupported action")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO txn(ts_code, trade_date, action, shares, price, amount, fee, notes) VALUES(?,?,?,?,?,?,?,?)",
            (data["ts_code"], date, action, shares, price, data.get("amount"), fee, data.get("notes",""))
        )
        row = conn.execute("SELECT shares, avg_cost FROM position WHERE ts_code=?", (data["ts_code"],)).fetchone()
        old_shares, old_cost = (row["shares"], row["avg_cost"]) if row else (0.0, 0.0)

        if action == "BUY":
            new_shares = old_shares + abs(shares)
            total_cost = old_shares * old_cost + abs(shares) * price + fee
            new_cost = (total_cost / new_shares) if new_shares > 0 else 0.0
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (data["ts_code"], new_shares, new_cost, date))
        elif action == "SELL":
            new_shares = round(old_shares + shares, 8)
            if new_shares < -1e-6:
                conn.rollback()
                raise ValueError("Sell exceeds current shares")
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (data["ts_code"], new_shares, old_cost if new_shares > 0 else 0.0, date))
        conn.commit()
        pos = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (data["ts_code"],)).fetchone()
    result = {"ts_code": pos["ts_code"], "shares": pos["shares"], "avg_cost": pos["avg_cost"]}
    log.set_entity("TXN", f"{cur.lastrowid}")
    log.set_after({"position": result})
    return result

def bulk_txn(rows: list[dict], log: LogContext) -> dict:
    """批量写入交易（通常用于把历史BUY一次性导入作为建仓记录）"""
    ok, fail = 0, 0
    errs = []
    for i, r in enumerate(rows):
        try:
            # 复用已有 create_txn 逻辑（含均价法/卖出校验）
            create_txn(r, log)
            ok += 1
        except Exception as e:
            fail += 1
            errs.append({"index": i, "ts_code": r.get("ts_code"), "error": str(e)})
    log.set_after({"ok": ok, "fail": fail})
    return {"ok": ok, "fail": fail, "errors": errs}
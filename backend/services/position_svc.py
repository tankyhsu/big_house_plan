# backend/services/position_svc.py
from typing import Optional, List, Dict, Any
from ..db import get_conn
from ..logs import LogContext

# ===== Position Raw CRUD =====
def list_positions_raw(include_zero: bool = True) -> list[dict]:
    sql = """
    SELECT p.ts_code, p.shares, p.avg_cost, p.last_update,
           i.name AS inst_name, i.category_id, i.type AS inst_type, i.active,
           c.name AS cat_name, c.sub_name AS cat_sub
    FROM position p
    LEFT JOIN instrument i ON i.ts_code = p.ts_code
    LEFT JOIN category c ON c.id = i.category_id
    """
    if not include_zero: sql += " WHERE p.shares > 0"
    sql += " ORDER BY c.name, c.sub_name, p.ts_code"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

def set_opening_position(ts_code: str, shares: float, avg_cost: float, date: str, log: LogContext):
    with get_conn() as conn:
        before = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        if before: before = dict(before)
        conn.execute(
            "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
            (ts_code, float(shares), float(avg_cost), date)
        )
        conn.commit()
        after = conn.execute("SELECT ts_code, shares, avg_cost, last_update FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code); 
    log.set_before(before); 
    log.set_after(after)
    return after

def update_position_one(ts_code: str, shares: float|None, avg_cost: float|None, date: str, log: LogContext):
    with get_conn() as conn:
        before = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        if before: before = dict(before)
        if shares is None and avg_cost is None:
            raise ValueError("at least one of shares/avg_cost must be provided")
        if shares is not None and shares < 0:
            raise ValueError("shares cannot be negative")
        if before is None:
            conn.execute("INSERT INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (ts_code, float(shares or 0.0), float(avg_cost or 0.0), date))
        else:
            new_shares = float(shares if shares is not None else before["shares"])
            new_cost = float(avg_cost if avg_cost is not None else before["avg_cost"])
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (ts_code, new_shares, new_cost, date))
        conn.commit()
        after = conn.execute("SELECT ts_code, shares, avg_cost, last_update FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code); log.set_before(before); log.set_after(after)
    return after

def delete_position(ts_code: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM position WHERE ts_code=?", (ts_code,))
        conn.commit()
        return cur.rowcount

def cleanup_zero_positions() -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM position WHERE shares <= 0")
        conn.commit()
        return cur.rowcount
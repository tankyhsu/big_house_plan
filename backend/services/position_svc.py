# backend/services/position_svc.py
from typing import Optional, List, Dict, Any
from ..db import get_conn
from ..logs import LogContext
from ..repository import position_repo

# ===== Position Raw CRUD =====
def list_positions_raw(include_zero: bool = True) -> list[dict]:
    with get_conn() as conn:
        rows = position_repo.list_positions_raw(conn, include_zero)
        return [dict(r) for r in rows]

def set_opening_position(ts_code: str, shares: float, avg_cost: float, date: str, log: LogContext, opening_date: Optional[str] = None):
    od = opening_date or date  # 默认与最后更新一致
    with get_conn() as conn:
        before = position_repo.get_position_full(conn, ts_code)
        if before: before = dict(before)
        position_repo.upsert_opening_position(conn, ts_code, float(shares), float(avg_cost), date, od)
        conn.commit()
        after = position_repo.get_position_full(conn, ts_code)
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code); 
    log.set_before(before); 
    log.set_after(after)
    return after

def update_position_one(ts_code: str, shares: Optional[float], avg_cost: Optional[float], date: str, log: LogContext, opening_date: Optional[str] = None):
    with get_conn() as conn:
        before = conn.execute("SELECT ts_code, shares, avg_cost, opening_date FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        if before: before = dict(before)
        if shares is None and avg_cost is None:
            raise ValueError("at least one of shares/avg_cost must be provided")
        if shares is not None and shares < 0:
            raise ValueError("shares cannot be negative")
        if before is None:
            od = opening_date or date
            position_repo.upsert_position_with_opening(conn, ts_code, float(shares or 0.0), float(avg_cost or 0.0), date, od)
        else:
            new_shares = float(shares if shares is not None else before["shares"])
            new_cost = float(avg_cost if avg_cost is not None else before["avg_cost"])
            od = opening_date if opening_date is not None else before.get("opening_date") or date
            position_repo.upsert_position_with_opening(conn, ts_code, new_shares, new_cost, date, od)
        conn.commit()
        after = conn.execute("SELECT ts_code, shares, avg_cost, last_update, opening_date FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code); log.set_before(before); log.set_after(after)
    return after

def delete_position(ts_code: str) -> int:
    with get_conn() as conn:
        cur = position_repo.delete_position(conn, ts_code)
        conn.commit()
        return cur

def cleanup_zero_positions() -> int:
    """清理零持仓，并将清理的标的自动加入自选"""
    from ..repository import watchlist_repo
    
    with get_conn() as conn:
        # 先获取即将被清理的零持仓标的
        cursor = conn.execute("SELECT ts_code FROM position WHERE shares <= 0")
        zero_position_codes = [row[0] for row in cursor.fetchall()]
        
        # 清理零持仓
        cur = position_repo.cleanup_zero_positions(conn)
        
        # 将清理的标的加入自选（如果不存在的话）
        for ts_code in zero_position_codes:
            if not watchlist_repo.exists(conn, ts_code):
                try:
                    watchlist_repo.add(conn, ts_code, "自动从零持仓移入")
                except Exception:
                    # 忽略添加失败的情况（比如instrument不存在）
                    pass
        
        conn.commit()
        return cur

from __future__ import annotations

from typing import Any
from .utils import yyyyMMdd_to_dash
from ..db import get_conn
from ..repository import watchlist_repo, price_repo, instrument_repo


def ensure_watchlist_schema():
    with get_conn() as conn:
        watchlist_repo.ensure_schema(conn)
        conn.commit()


def add_to_watchlist(ts_code: str, note: str | None = None):
    with get_conn() as conn:
        # 确保 instrument 中存在该代码
        row = instrument_repo.get_one(conn, ts_code)
        if not row:
            raise ValueError("instrument_not_found")
        watchlist_repo.add(conn, ts_code, note)
        conn.commit()


def remove_from_watchlist(ts_code: str):
    with get_conn() as conn:
        watchlist_repo.remove(conn, ts_code)
        conn.commit()


def list_watchlist(with_last_price: bool = True, on_date_yyyymmdd: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = watchlist_repo.list_all(conn)
        items: list[dict[str, Any]] = []
        last_date_dash = None
        if with_last_price:
            from datetime import datetime
            d = on_date_yyyymmdd or datetime.now().strftime("%Y%m%d")
            last_date_dash = yyyyMMdd_to_dash(d)
        
        # 获取当前持仓信息以判断是否已持仓
        position_codes = set()
        cursor = conn.execute("SELECT ts_code FROM position WHERE shares > 0")
        for pos_row in cursor.fetchall():
            position_codes.add(pos_row[0])
        
        for r in rows:
            it = {
                "ts_code": r["ts_code"],
                "name": r["name"],
                "type": r["type"],
                "active": bool(r["active"]) if ("active" in r.keys()) else None,
                "category_id": r["category_id"],
                "note": r["note"],
                "created_at": r["created_at"],
                "has_position": r["ts_code"] in position_codes,  # 是否已持仓
            }
            if with_last_price and last_date_dash:
                last = price_repo.get_last_close_on_or_before(conn, r["ts_code"], last_date_dash)
                it["last_price"] = None if not last else float(last[1])
                it["last_price_date"] = None if not last else last[0]
                
                # 计算涨跌幅
                if last and last[0]:  # 如果有最新价格数据
                    price_change = price_repo.get_price_change_percentage(conn, r["ts_code"], last[0])
                    it["price_change"] = price_change
                else:
                    it["price_change"] = None
            items.append(it)
        return items


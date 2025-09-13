from __future__ import annotations

from sqlite3 import Connection


def get_position(conn: Connection, ts_code: str):
    return conn.execute(
        "SELECT shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)
    ).fetchone()


def upsert_position(conn: Connection, ts_code: str, shares: float, avg_cost: float, last_update: str):
    conn.execute(
        "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
        (ts_code, float(shares), float(avg_cost), last_update),
    )


def upsert_position_with_opening(conn: Connection, ts_code: str, shares: float, avg_cost: float, last_update: str, opening_date: str):
    conn.execute(
        "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update, opening_date) VALUES(?,?,?,?,?)",
        (ts_code, float(shares), float(avg_cost), last_update, opening_date),
    )


def get_position_full(conn: Connection, ts_code: str):
    return conn.execute(
        "SELECT ts_code, shares, avg_cost, last_update, opening_date FROM position WHERE ts_code=?",
        (ts_code,),
    ).fetchone()


def upsert_opening_position(
    conn: Connection,
    ts_code: str,
    shares: float,
    avg_cost: float,
    last_update: str,
    opening_date: str,
):
    conn.execute(
        "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update, opening_date) VALUES(?,?,?,?,?)",
        (ts_code, float(shares), float(avg_cost), last_update, opening_date),
    )


def list_positions_raw(conn: Connection, include_zero: bool = False, with_price: bool = True, on_date_yyyymmdd: str | None = None):
    from .price_repo import get_last_close_on_or_before, get_price_change_percentage
    from ..services.utils import yyyyMMdd_to_dash
    from datetime import datetime
    
    sql = """
    SELECT p.ts_code, p.shares, p.avg_cost, p.last_update, p.opening_date,
           i.name AS inst_name, i.category_id, i.type AS inst_type, i.active,
           c.name AS cat_name, c.sub_name AS cat_sub
    FROM position p
    LEFT JOIN instrument i ON i.ts_code = p.ts_code
    LEFT JOIN category c ON c.id = i.category_id
    """
    if not include_zero:
        sql += " WHERE p.shares > 0"
    sql += " ORDER BY c.name, c.sub_name, p.ts_code"
    
    rows = conn.execute(sql).fetchall()
    
    if not with_price:
        return rows
    
    # Add price data
    last_date_dash = None
    if with_price:
        d = on_date_yyyymmdd or datetime.now().strftime("%Y%m%d")
        last_date_dash = yyyyMMdd_to_dash(d)
    
    enhanced_rows = []
    for row in rows:
        row_dict = dict(row)
        
        if with_price and last_date_dash:
            # Get latest price
            last_price_data = get_last_close_on_or_before(conn, row["ts_code"], last_date_dash)
            if last_price_data:
                row_dict["last_price"] = float(last_price_data[1])
                row_dict["last_price_date"] = last_price_data[0]
                
                # Calculate price change
                price_change = get_price_change_percentage(conn, row["ts_code"], last_price_data[0])
                row_dict["price_change"] = price_change
            else:
                row_dict["last_price"] = None
                row_dict["last_price_date"] = None
                row_dict["price_change"] = None
        
        enhanced_rows.append(row_dict)
    
    return enhanced_rows


def delete_position(conn: Connection, ts_code: str) -> int:
    cur = conn.execute("DELETE FROM position WHERE ts_code=?", (ts_code,))
    return cur.rowcount




def list_position_codes_with_shares(conn: Connection) -> list[str]:
    return [r["ts_code"] for r in conn.execute("SELECT ts_code FROM position WHERE shares>0").fetchall()]

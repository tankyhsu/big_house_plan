from typing import Optional
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


def list_positions_raw(conn: Connection, include_zero: bool = True):
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
    return conn.execute(sql).fetchall()


def delete_position(conn: Connection, ts_code: str) -> int:
    cur = conn.execute("DELETE FROM position WHERE ts_code=?", (ts_code,))
    return cur.rowcount


def cleanup_zero_positions(conn: Connection) -> int:
    cur = conn.execute("DELETE FROM position WHERE shares <= 0")
    return cur.rowcount


def list_position_codes_with_shares(conn: Connection) -> list[str]:
    return [r["ts_code"] for r in conn.execute("SELECT ts_code FROM position WHERE shares>0").fetchall()]

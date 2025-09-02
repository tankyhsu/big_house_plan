from typing import Optional
from sqlite3 import Connection


def clear_day(conn: Connection, date_dash: str):
    conn.execute("DELETE FROM portfolio_daily WHERE trade_date=?", (date_dash,))
    conn.execute("DELETE FROM category_daily WHERE trade_date=?", (date_dash,))


def upsert_portfolio_daily(
    conn: Connection,
    date_dash: str,
    ts_code: str,
    market_value: float,
    cost: float,
    unrealized_pnl: float,
    ret: Optional[float],
    category_id: Optional[int],
):
    conn.execute(
        """INSERT OR REPLACE INTO portfolio_daily
               (trade_date, ts_code, market_value, cost, unrealized_pnl, ret, category_id)
               VALUES (?,?,?,?,?,?,?)""",
        (date_dash, ts_code, market_value, cost, unrealized_pnl, ret, category_id),
    )


def upsert_category_daily(
    conn: Connection,
    date_dash: str,
    category_id: int,
    market_value: float,
    cost: float,
    pnl: float,
    ret: Optional[float],
    overweight: int,
):
    conn.execute(
        """INSERT OR REPLACE INTO category_daily
               (trade_date, category_id, market_value, cost, pnl, ret, overweight)
               VALUES (?,?,?,?,?,?,?)""",
        (date_dash, category_id, market_value, cost, pnl, ret, overweight),
    )


def insert_signal_category(conn: Connection, date_dash: str, category_id: int, level: str, typ: str, message: str):
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND category_id=? AND type=?",
        (date_dash, category_id, typ)
    ).fetchone()
    
    if not existing:
        conn.execute(
            "INSERT INTO signal(trade_date, category_id, level, type, message) VALUES (?,?,?,?,?)",
            (date_dash, category_id, level, typ, message),
        )


def insert_signal_instrument(conn: Connection, date_dash: str, ts_code: str, level: str, typ: str, message: str):
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
        (date_dash, ts_code, typ)
    ).fetchone()
    
    if not existing:
        conn.execute(
            "INSERT INTO signal(trade_date, ts_code, level, type, message) VALUES (?,?,?,?,?)",
            (date_dash, ts_code, level, typ, message),
        )


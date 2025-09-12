from __future__ import annotations

from sqlite3 import Connection


def insert_txn(
    conn: Connection,
    ts_code: str,
    trade_date: str,
    action: str,
    shares: float,
    price: float | None,
    amount: float | None,
    fee: float | None,
    notes: str | None,
    group_id: int | None = None,
    realized_pnl: float | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO txn(ts_code, trade_date, action, shares, price, amount, fee, notes, group_id, realized_pnl) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (ts_code, trade_date, action, shares, price, amount, fee, notes, group_id, realized_pnl),
    )
    return int(cur.lastrowid)


def update_group_id(conn: Connection, rowid: int, group_id: int) -> None:
    conn.execute("UPDATE txn SET group_id=? WHERE rowid=?", (group_id, rowid))


def count_all(conn: Connection) -> int:
    return int(conn.execute("SELECT COUNT(1) AS c FROM txn").fetchone()["c"])


def list_txn_page(conn: Connection, page: int, size: int):
    return conn.execute(
        "SELECT rowid as id, ts_code, trade_date, action, shares, price, amount, fee, notes, group_id, realized_pnl "
        "FROM txn ORDER BY trade_date DESC, rowid DESC LIMIT ? OFFSET ?",
        (size, (page - 1) * size),
    ).fetchall()


def list_txns_for_code_ordered(conn: Connection, ts_code: str):
    return conn.execute(
        "SELECT rowid AS id, action, shares, price, fee FROM txn "
        "WHERE ts_code=? AND action != 'ADJ' "
        "ORDER BY trade_date ASC, rowid ASC",
        (ts_code,),
    ).fetchall()


def list_txns_for_code_upto(conn: Connection, ts_code: str, date_dash: str):
    return conn.execute(
        "SELECT rowid AS id, trade_date, action, shares, price, fee, amount FROM txn "
        "WHERE ts_code=? AND trade_date<=? ORDER BY trade_date ASC, rowid ASC",
        (ts_code, date_dash),
    ).fetchall()


def list_txn_codes_distinct(conn: Connection) -> list[str]:
    return [r["ts_code"] for r in conn.execute("SELECT DISTINCT ts_code FROM txn").fetchall()]

def get_monthly_realized_pnl(conn: Connection):
    """获取所有SELL交易的realized_pnl数据，按月份分组统计"""
    return conn.execute(
        "SELECT trade_date, realized_pnl "
        "FROM txn "
        "WHERE action = 'SELL' "
        "AND realized_pnl IS NOT NULL "
        "AND realized_pnl != 0 "
        "ORDER BY trade_date DESC"
    ).fetchall()


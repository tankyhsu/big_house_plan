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
) -> int:
    cur = conn.execute(
        "INSERT INTO txn(ts_code, trade_date, action, shares, price, amount, fee, notes, group_id) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (ts_code, trade_date, action, shares, price, amount, fee, notes, group_id),
    )
    return int(cur.lastrowid)


def update_group_id(conn: Connection, rowid: int, group_id: int) -> None:
    conn.execute("UPDATE txn SET group_id=? WHERE rowid=?", (group_id, rowid))


def count_all(conn: Connection) -> int:
    return int(conn.execute("SELECT COUNT(1) AS c FROM txn").fetchone()["c"])


def list_txn_page(conn: Connection, page: int, size: int):
    return conn.execute(
        "SELECT rowid as id, ts_code, trade_date, action, shares, price, amount, fee, notes, group_id "
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

def list_txns_for_code_with_date_ordered(conn: Connection, ts_code: str):
    """获取包含trade_date的交易记录，按时间顺序，排除ADJ类型交易（包含现金镜像交易）"""
    return conn.execute(
        "SELECT rowid AS id, action, shares, price, fee, trade_date FROM txn "
        "WHERE ts_code=? AND action != 'ADJ' "
        "ORDER BY trade_date ASC, rowid ASC",
        (ts_code,),
    ).fetchall()

def get_sell_transaction_codes(conn: Connection):
    """获取所有有SELL交易的标的代码，排除ADJ类型交易（包含现金镜像交易）"""
    return conn.execute(
        "SELECT DISTINCT ts_code FROM txn "
        "WHERE action = 'SELL' AND action != 'ADJ' "
        "ORDER BY ts_code"
    ).fetchall()

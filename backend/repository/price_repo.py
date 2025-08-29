from typing import Optional, Tuple
from sqlite3 import Connection


def get_last_close_on_or_before(conn: Connection, ts_code: str, date_dash: str) -> Optional[Tuple[str, float]]:
    row = conn.execute(
        "SELECT trade_date, close FROM price_eod WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
        (ts_code, date_dash),
    ).fetchone()
    if not row:
        return None
    if row["close"] is None:
        return None
    return row["trade_date"], float(row["close"])  # (YYYY-MM-DD, close)


def upsert_price_eod_many(conn: Connection, bars: list[dict]):
    if not bars:
        return 0
    sql = (
        "INSERT INTO price_eod (ts_code, trade_date, close, pre_close, open, high, low, vol, amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(ts_code, trade_date) DO UPDATE SET "
        "close=excluded.close, pre_close=excluded.pre_close, open=excluded.open, high=excluded.high, "
        "low=excluded.low, vol=excluded.vol, amount=excluded.amount"
    )
    n = 0
    for b in bars:
        conn.execute(
            sql,
            (
                b.get("ts_code"),
                b.get("trade_date"),
                b.get("close"),
                b.get("pre_close"),
                b.get("open"),
                b.get("high"),
                b.get("low"),
                b.get("vol"),
                b.get("amount"),
            ),
        )
        n += 1
    conn.commit()
    return n

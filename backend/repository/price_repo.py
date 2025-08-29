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


from sqlite3 import Connection
from typing import Optional


def ensure_schema(conn: Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            ts_code TEXT PRIMARY KEY,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def add(conn: Connection, ts_code: str, note: Optional[str] = None):
    conn.execute(
        "INSERT OR IGNORE INTO watchlist(ts_code, note) VALUES(?, ?)",
        (ts_code, note),
    )


def remove(conn: Connection, ts_code: str):
    conn.execute("DELETE FROM watchlist WHERE ts_code=?", (ts_code,))


def list_all(conn: Connection):
    sql = (
        "SELECT w.ts_code, COALESCE(w.note,'') AS note, w.created_at, "
        "i.name, i.type, i.active, i.category_id "
        "FROM watchlist w LEFT JOIN instrument i ON i.ts_code = w.ts_code "
        "ORDER BY w.created_at DESC"
    )
    return conn.execute(sql).fetchall()


def exists(conn: Connection, ts_code: str) -> bool:
    row = conn.execute("SELECT 1 FROM watchlist WHERE ts_code=?", (ts_code,)).fetchone()
    return row is not None


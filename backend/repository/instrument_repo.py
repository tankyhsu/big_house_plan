from typing import Dict, Iterable, Optional
from sqlite3 import Connection


def get_type(conn: Connection, ts_code: str) -> str:
    row = conn.execute("SELECT COALESCE(type,'') AS t FROM instrument WHERE ts_code=?", (ts_code,)).fetchone()
    return (row["t"] or "") if row else ""


def name_map_for(conn: Connection, codes: Iterable[str]) -> Dict[str, str]:
    codes = list(codes)
    if not codes:
        return {}
    q = "SELECT ts_code, name FROM instrument WHERE ts_code IN ({})".format(
        ",".join(["?"] * len(codes))
    )
    out: Dict[str, str] = {}
    for r in conn.execute(q, codes).fetchall():
        out[r["ts_code"]] = r["name"]
    return out


def type_map_for(conn: Connection, codes: Iterable[str]) -> Dict[str, str]:
    codes = list(codes)
    if not codes:
        return {}
    q = "SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE ts_code IN ({})".format(
        ",".join(["?"] * len(codes))
    )
    out: Dict[str, str] = {}
    for r in conn.execute(q, codes).fetchall():
        out[r["ts_code"]] = (r["t"] or "")
    return out


def upsert_instrument(conn: Connection, ts_code: str, name: str, sec_type: str, category_id: int, active: bool):
    conn.execute(
        "INSERT OR REPLACE INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,?)",
        (ts_code, name, sec_type, int(category_id), 1 if active else 0),
    )


def list_instruments(conn: Connection, q: Optional[str], active_only: bool):
    sql = """
    SELECT i.ts_code, i.name, i.active, i.category_id, i.type,
           c.name AS cat_name, c.sub_name AS cat_sub
    FROM instrument i
    LEFT JOIN category c ON c.id = i.category_id
    """
    where = []
    params: dict = {}
    if active_only:
        where.append("i.active = 1")
    if q:
        where.append("(i.ts_code LIKE :q OR i.name LIKE :q)")
        params["q"] = f"%{q}%"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.name, c.sub_name, i.ts_code"
    return conn.execute(sql, params).fetchall()


def set_active(conn: Connection, ts_code: str, active: bool):
    conn.execute("UPDATE instrument SET active=? WHERE ts_code=?", (1 if active else 0, ts_code))


def list_active_non_cash_codes(conn: Connection) -> list[str]:
    rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE active=1").fetchall()
    out = []
    for r in rows:
        if (r["t"] or "").upper() != "CASH":
            out.append(r["ts_code"])
    return out


def get_one(conn: Connection, ts_code: str):
    sql = (
        "SELECT i.ts_code, i.name, i.type, i.active, i.category_id, "
        "c.name AS cat_name, c.sub_name AS cat_sub "
        "FROM instrument i LEFT JOIN category c ON c.id = i.category_id "
        "WHERE i.ts_code = ?"
    )
    return conn.execute(sql, (ts_code,)).fetchone()

from ..db import get_conn
from ..logs import LogContext

def create_category(name: str, sub_name: str, target_units: float, log: LogContext) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
            (name, sub_name, float(target_units))
        )
        conn.commit()
        new_id = cur.lastrowid
    log.set_entity("CATEGORY", str(new_id))
    log.set_after({"id": new_id, "name": name, "sub_name": sub_name, "target_units": target_units})
    return new_id


# ===== Category list for UI =====
def list_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, sub_name, target_units FROM category ORDER BY name, sub_name").fetchall()
        return [dict(r) for r in rows]

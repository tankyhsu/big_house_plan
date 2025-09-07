from __future__ import annotations

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


def update_category(category_id: int, *, sub_name: str | None = None, target_units: float | None = None, log: LogContext) -> dict:
    """
    Update editable fields of a category. Major category `name` is immutable.
    Editable fields: sub_name (2nd level), target_units.
    Returns the updated row as dict.
    """
    if sub_name is None and target_units is None:
        raise ValueError("at least one of sub_name/target_units must be provided")

    with get_conn() as conn:
        before = conn.execute(
            "SELECT id, name, sub_name, target_units FROM category WHERE id=?",
            (category_id,)
        ).fetchone()
        if before is None:
            raise ValueError("category_not_found")
        before_dict = dict(before)

        fields = []
        params: list[object] = []
        if sub_name is not None:
            fields.append("sub_name=?")
            params.append(sub_name)
        if target_units is not None:
            fields.append("target_units=?")
            params.append(float(target_units))
        params.append(category_id)

        sql = f"UPDATE category SET {', '.join(fields)} WHERE id=?"
        conn.execute(sql, params)
        conn.commit()

        after = conn.execute(
            "SELECT id, name, sub_name, target_units FROM category WHERE id=?",
            (category_id,)
        ).fetchone()
        after_dict = dict(after) if after else None

    log.set_entity("CATEGORY", str(category_id))
    log.set_before(before_dict)
    log.set_after(after_dict)
    return after_dict

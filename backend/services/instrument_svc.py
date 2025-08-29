# backend/services/instrument_svc.py
from ..db import get_conn
from ..logs import LogContext
from typing import Optional

def create_instrument(ts_code: str, name: str, category_id: int, active: bool, log: LogContext, sec_type: str | None = None):
    """创建/更新标的；sec_type 可为 STOCK | FUND | CASH 。None 时不覆盖既有值。"""
    def _norm_type(t: str | None) -> str:
        t = (t or "").upper().strip()
        if t in ("STOCK", "FUND", "CASH"): 
            return t
        return "STOCK"  # 兜底：无法判断时默认 STOCK

    with get_conn() as conn:
        old = conn.execute("SELECT type FROM instrument WHERE ts_code=?", (ts_code,)).fetchone()
        final_type = _norm_type(sec_type or (old["type"] if old and old["type"] else None))
        conn.execute(
            "INSERT OR REPLACE INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,?)",
            (ts_code, name, final_type, int(category_id), 1 if active else 0)
        )
        conn.commit()
    log.set_entity("INSTRUMENT", ts_code)
    log.set_after({"ts_code": ts_code, "name": name, "category_id": category_id, "active": active, "type": final_type})

# ===== Instrument List (for autocomplete) =====
def list_instruments(q: Optional[str] = None, active_only: bool = True) -> list[dict]:
    sql = """
    SELECT i.ts_code, i.name, i.active, i.category_id, i.type,
           c.name AS cat_name, c.sub_name AS cat_sub
    FROM instrument i
    LEFT JOIN category c ON c.id = i.category_id
    """
    where = []
    params = {}
    if active_only:
        where.append("i.active = 1")
    if q:
        where.append("(i.ts_code LIKE :q OR i.name LIKE :q)")
        params["q"] = f"%{q}%"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.name, c.sub_name, i.ts_code"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def seed_load(categories_csv: str, instruments_csv: str, log: LogContext) -> dict:
    """从 CSV 导入类别与标的映射；CSV 要含必要列：
       categories.csv: name, sub_name, target_units
       instruments.csv: ts_code, name, category_name, category_sub_name, active(0/1)
       如果 instrument 指定的分类不存在，则自动创建。
    """
    cat_df = pd.read_csv(categories_csv)
    ins_df = pd.read_csv(instruments_csv)

    created_cat = 0
    created_ins = 0

    with get_conn() as conn:
        # 先建分类（若已存在则跳过）
        for _, r in cat_df.iterrows():
            name = str(r["name"]).strip()
            sub = str(r.get("sub_name", "")).strip()
            target_units = float(r["target_units"])
            row = conn.execute(
                "SELECT id FROM category WHERE name=? AND sub_name=?", (name, sub)
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
                    (name, sub, target_units)
                )
                created_cat += 1
        conn.commit()

        # 读取分类字典
        rows = conn.execute("SELECT id, name, sub_name FROM category").fetchall()
        cat_map = {(r["name"], r["sub_name"]): r["id"] for r in rows}

        # 再建标的
        for _, r in ins_df.iterrows():
            ts = str(r["ts_code"]).strip()
            nm = str(r["name"]).strip()
            cn = str(r["category_name"]).strip()
            cs = str(r.get("category_sub_name", "")).strip()
            active = int(r.get("active", 1))
            cat_id = cat_map.get((cn, cs))
            if cat_id is None:
                # 若分类不存在，自动创建
                cur = conn.execute(
                    "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
                    (cn, cs, 0.0)
                )
                conn.commit()
                cat_id = cur.lastrowid
                cat_map[(cn, cs)] = cat_id
                created_cat += 1
            conn.execute(
                "INSERT OR REPLACE INTO instrument(ts_code, name, category_id, active) VALUES(?,?,?,?)",
                (ts, nm, int(cat_id), 1 if active else 0)
            )
            created_ins += 1
        conn.commit()

    log.set_after({"created_category": created_cat, "created_instrument": created_ins})
    return {"created_category": created_cat, "created_instrument": created_ins}

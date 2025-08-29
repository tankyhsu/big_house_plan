# backend/services/instrument_svc.py
from ..db import get_conn
from ..logs import LogContext
from typing import Optional
import pandas as pd
from ..repository import instrument_repo

def create_instrument(ts_code: str, name: str, category_id: int, active: bool, log: LogContext, sec_type: str | None = None):
    """创建/更新标的；sec_type 可为 STOCK | FUND | CASH 。None 时不覆盖既有值。"""
    def _norm_type(t: str | None) -> str:
        t = (t or "").upper().strip()
        if t in ("STOCK", "FUND", "CASH"): 
            return t
        return "STOCK"  # 兜底：无法判断时默认 STOCK

    with get_conn() as conn:
        old_t = instrument_repo.get_type(conn, ts_code)
        final_type = _norm_type(sec_type or (old_t if old_t else None))
        instrument_repo.upsert_instrument(conn, ts_code, name, final_type, int(category_id), bool(active))
        conn.commit()
    log.set_entity("INSTRUMENT", ts_code)
    log.set_after({"ts_code": ts_code, "name": name, "category_id": category_id, "active": active, "type": final_type})

# ===== Instrument List (for autocomplete) =====
def list_instruments(q: Optional[str] = None, active_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        rows = instrument_repo.list_instruments(conn, q, active_only)
        return [dict(r) for r in rows]


def seed_load(categories_csv: str, instruments_csv: str, log: LogContext) -> dict:
    """从 CSV 导入类别与标的映射；CSV 要含必要列：
       categories.csv: name, sub_name, target_units
       instruments.csv: ts_code, name, type, currency, category_name, category_sub_name, active(0/1)
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
            tp_raw = str(r.get("type", "")).strip().upper()
            tp = "ETF" if tp_raw == "ETF" else ("CASH" if tp_raw == "CASH" else ("FUND" if tp_raw == "FUND" else "STOCK"))
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
            instrument_repo.upsert_instrument(conn, ts, nm, tp, int(cat_id), bool(active))
            created_ins += 1
        conn.commit()

    log.set_after({"created_category": created_cat, "created_instrument": created_ins})
    return {"created_category": created_cat, "created_instrument": created_ins}

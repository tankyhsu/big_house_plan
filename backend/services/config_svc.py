# backend/services/config_svc.py
from ..db import get_conn
from ..logs import LogContext
from .utils import to_float_safe

def get_config() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key,value FROM config").fetchall()
        cfg = {r["key"]: r["value"] for r in rows}
    out = {
        "unit_amount": to_float_safe(cfg.get("unit_amount"), 3000.0),
        "stop_gain_pct": to_float_safe(cfg.get("stop_gain_pct"), 0.30),
        "overweight_band": to_float_safe(cfg.get("overweight_band"), 0.20),
        "ma_short": int(to_float_safe(cfg.get("ma_short"), 20) or 20),
        "ma_long": int(to_float_safe(cfg.get("ma_long"), 60) or 60),
        "ma_risk": int(to_float_safe(cfg.get("ma_risk"), 200) or 200),
        "tushare_token": cfg.get("tushare_token"),
    }
    return out

def update_config(upd: dict, log: LogContext) -> list[str]:
    updated = []
    with get_conn() as conn:
        before = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config")}
        for k, v in upd.items():
            conn.execute(
                "INSERT INTO config(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, str(v))
            )
            updated.append(k)
        conn.commit()
        after = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config")}
    log.set_before(before); log.set_after(after)
    return updated
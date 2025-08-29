# backend/services/config_svc.py
from ..db import get_conn
from ..logs import LogContext
from .utils import to_float_safe

DEFAULTS = {
    "unit_amount": "3000",
    "stop_gain_pct": "0.30",
    "overweight_band": "0.20",
    "ma_short": "20",
    "ma_long": "60",
    "ma_risk": "200",
    "tushare_token": "",   # 如果需要，可以留空
    # 现金镜像所使用的现金标的代码（需在 instrument 表中存在并设为 active）。
    # 默认与 seeds/instruments.csv 保持一致。
    "cash_ts_code": "CASH.CNY",
}

def ensure_default_config():
    """确保关键配置存在（不覆盖已有值）"""
    with get_conn() as conn:
        for k, v in DEFAULTS.items():
            conn.execute(
                "INSERT INTO config(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO NOTHING",
                (k, v),
            )
        conn.commit()

def get_config() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    cfg = {r["key"]: r["value"] for r in rows}

    # 转换为正确类型 & 默认兜底
    out = {
        "unit_amount": int(cfg.get("unit_amount", DEFAULTS["unit_amount"])),
        "stop_gain_pct": float(cfg.get("stop_gain_pct", DEFAULTS["stop_gain_pct"])),
        "overweight_band": float(cfg.get("overweight_band", DEFAULTS["overweight_band"])),
        "ma_short": int(cfg.get("ma_short", DEFAULTS["ma_short"])),
        "ma_long": int(cfg.get("ma_long", DEFAULTS["ma_long"])),
        "ma_risk": int(cfg.get("ma_risk", DEFAULTS["ma_risk"])),
        "tushare_token": cfg.get("tushare_token", DEFAULTS["tushare_token"]),
        "cash_ts_code": cfg.get("cash_ts_code", DEFAULTS["cash_ts_code"]),
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

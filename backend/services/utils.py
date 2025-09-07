from __future__ import annotations

# backend/services/utils.py
from ..db import get_conn  # 供其他svc继续复用

def yyyyMMdd_to_dash(s: str) -> str: return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"

def to_float_safe(x, default=None):
    try: return float(x)
    except: return default

# 统一的“最近可用价”SQL片段（避免散落多处写错）
RECENT_CLOSE_SQL = """
(SELECT close FROM price_eod pe
  WHERE pe.ts_code = :ts_code AND pe.trade_date <= :date
  ORDER BY pe.trade_date DESC LIMIT 1)
"""
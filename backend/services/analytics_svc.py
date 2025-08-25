# backend/services/analytics_svc.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from datetime import datetime, date as dt_date
from math import isfinite

from ..db import get_conn
from .utils import yyyyMMdd_to_dash

# analytics_svc.py 头部
import time, traceback
from datetime import datetime, date as dt_date
from math import isfinite

def _alog(msg: str):
    # 统一前缀，便于在控制台检索
    print(f"[analytics][xirr] {msg}")

def _xirr(cashflows: List[Tuple[str, float]]) -> Optional[float]:
    # 规范日期并过滤非法记录（容错：YYYY-MM-DD / YYYYMMDD）
    def _to_dash_date(s: Optional[str]) -> Optional[str]:
        if not s: return None
        s = str(s).strip()
        if len(s) == 10 and s[4] == "-" and s[7] == "-": return s
        if len(s) == 8 and s.isdigit(): return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        try:
            dt = datetime.fromisoformat(s); return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    if not cashflows:
        _alog("xirr: empty cashflows"); return None

    norm: List[Tuple[str, float]] = []
    for d, a in cashflows:
        dd = _to_dash_date(d)
        if dd is not None:
            norm.append((dd, float(a)))

    if len(norm) < 2:
        _alog(f"xirr: insufficient flows after normalize -> {len(norm)}")
        return None

    try:
        dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in norm]
    except Exception as e:
        _alog(f"xirr: date parse failed: {e}")
        return None

    t_end: dt_date = max(dates)
    days = [(t_end - d).days / 365.0 for d in dates]
    amounts = [a for _, a in norm]

    r = 0.10
    for _ in range(100):
        try:
            f = sum(a * (1 + r) ** t for a, t in zip(amounts, days))
            df = sum(a * t * (1 + r) ** (t - 1) for a, t in zip(amounts, days))
        except Exception as e:
            _alog(f"xirr: pow failed {e}")
            return None
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        if not isfinite(r_new):
            _alog("xirr: non-finite r_new"); return None
        if r_new < -0.999999:
            r_new = -0.999999
        if abs(r_new - r) < 1e-8:
            return r_new
        r = r_new
    _alog("xirr: not converged")
    return None

def _build_cashflows_for_ts(ts_code: str, date_dash: str) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[float]]:
    cfs: List[Tuple[str, float]] = []
    used_price_date: Optional[str] = None
    terminal_value: Optional[float] = None

    with get_conn() as conn:
        txns = conn.execute(
            """
            SELECT trade_date, action, shares, price, amount, fee
            FROM txn
            WHERE ts_code=? AND trade_date<=?
            ORDER BY trade_date ASC, rowid ASC
            """,
            (ts_code, date_dash)
        ).fetchall()
        _alog(f"build_cfs: ts={ts_code} date={date_dash} txns={len(txns)}")

        for t in txns:
            action = (t["action"] or "").upper()
            shares = float(t["shares"] or 0.0)
            price  = None if t["price"] is None else float(t["price"])
            amount = None if t["amount"] is None else float(t["amount"])
            fee    = float(t["fee"] or 0.0)
            d      = t["date"]  # 可能为 YYYY-MM-DD / YYYYMMDD

            if action == "BUY":
                gross = amount if amount is not None else (shares * (price or 0.0))
                cfs.append((d, -(gross + fee)))
            elif action == "SELL":
                gross = amount if amount is not None else (shares * (price or 0.0))
                cfs.append((d, +(gross - fee)))
            elif action == "DIV":
                cfs.append((d, +(amount or 0.0)))
            elif action == "FEE":
                cfs.append((d, -(fee if fee else (amount or 0.0))))
            elif action == "ADJ":
                if amount:
                    cfs.append((d, float(amount)))

        pos = conn.execute("SELECT shares FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        shares_now = float(pos["shares"] or 0.0) if pos else 0.0
        if shares_now > 0:
            pe = conn.execute(
                "SELECT close, trade_date FROM price_eod WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
                (ts_code, date_dash)
            ).fetchone()
            if pe and pe["close"] is not None:
                price = float(pe["close"])
                terminal_value = shares_now * price
                used_price_date = pe["trade_date"]  # YYYY-MM-DD
                cfs.append((date_dash, terminal_value))
        _alog(f"build_cfs: ts={ts_code} flows={len(cfs)} shares_now={shares_now} used_price_date={used_price_date} term={terminal_value}")
    return cfs, used_price_date, terminal_value


def compute_position_xirr(ts_code: str, date_yyyymmdd: str) -> Dict:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    t0 = time.time()
    _alog(f"compute_one: ts={ts_code} date={d} start")
    cfs, used_price_date, terminal_value = _build_cashflows_for_ts(ts_code, d)
    first_d = cfs[0][0] if cfs else None
    last_d  = cfs[-1][0] if cfs else None
    _alog(f"compute_one: ts={ts_code} flows={len(cfs)} first={first_d} last={last_d} used_price={used_price_date}")

    # --- 正常路径：有≥2笔现金流，走 XIRR ---
    if len(cfs) >= 2:
        try:
            r = _xirr(cfs)
            _alog(f"compute_one: ts={ts_code} r={r} elapsed_ms={int((time.time()-t0)*1000)}")
            return {
                "ts_code": ts_code,
                "date": d,
                "annualized_mwr": (float(r) if r is not None else None),
                "flows": len(cfs),
                "used_price_date": used_price_date,
                "terminal_value": terminal_value,
                "irr_reason": "ok" if r is not None else "no_solution"
            }
        except Exception as e:
            _alog(f"compute_one: ts={ts_code} EX {e}")
            traceback.print_exc()
            raise

    # --- Fallback 路径：无流水/不足两笔，用 建仓→估值 推算年化 ---
    try:
        from datetime import datetime as _dt
        with get_conn() as conn:
            # 取 position 的建仓信息
            prow = conn.execute(
                "SELECT opening_date, shares, avg_cost FROM position WHERE ts_code=?",
                (ts_code,)
            ).fetchone()
            if not prow:
                _alog(f"compute_one: ts={ts_code} no position row for fallback")
                return {
                    "ts_code": ts_code, "date": d,
                    "annualized_mwr": None, "flows": len(cfs),
                    "used_price_date": used_price_date, "terminal_value": terminal_value,
                    "irr_reason": "no_position"
                }

            opening_date_raw = prow["opening_date"]
            opening_date = _to_dash_date(opening_date_raw) if opening_date_raw else None
            shares_now = float(prow["shares"] or 0.0)
            avg_cost = float(prow["avg_cost"] or 0.0)

            if not opening_date or shares_now <= 0 or avg_cost <= 0:
                _alog(f"compute_one: ts={ts_code} fallback blocked "
                      f"opening_date={opening_date_raw} shares={shares_now} avg_cost={avg_cost}")
                return {
                    "ts_code": ts_code, "date": d,
                    "annualized_mwr": None, "flows": len(cfs),
                    "used_price_date": used_price_date, "terminal_value": terminal_value,
                    "irr_reason": "insufficient_base"
                }

            # 最近可用价（≤ 估值日）
            pe = conn.execute(
                "SELECT close, trade_date FROM price_eod WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
                (ts_code, d)
            ).fetchone()
            if not pe or pe["close"] is None:
                _alog(f"compute_one: ts={ts_code} fallback no price_eod <= {d}")
                return {
                    "ts_code": ts_code, "date": d,
                    "annualized_mwr": None, "flows": len(cfs),
                    "used_price_date": used_price_date, "terminal_value": terminal_value,
                    "irr_reason": "no_price"
                }

            price = float(pe["close"])
            used_price_date = pe["trade_date"]  # YYYY-MM-DD
            terminal_value = shares_now * price

            # 计算年化
            od = _dt.strptime(opening_date, "%Y-%m-%d").date()
            vd = _dt.strptime(d, "%Y-%m-%d").date()
            holding_days = (vd - od).days
            if holding_days <= 0:
                _alog(f"compute_one: ts={ts_code} fallback holding_days<=0 ({holding_days})")
                return {
                    "ts_code": ts_code, "date": d,
                    "annualized_mwr": None, "flows": len(cfs),
                    "used_price_date": used_price_date, "terminal_value": terminal_value,
                    "irr_reason": "invalid_holding_days"
                }

            total_return = (price / avg_cost) - 1.0
            annualized = (1.0 + total_return) ** (365.0 / holding_days) - 1.0

            _alog(f"compute_one: ts={ts_code} fallback annualized={annualized} "
                  f"total_return={total_return} days={holding_days} used_price={used_price_date}")
            return {
                "ts_code": ts_code,
                "date": d,
                "annualized_mwr": float(annualized),
                "flows": len(cfs),  # 这里一般为 0 或 1（只有期末市值）
                "used_price_date": used_price_date,
                "terminal_value": terminal_value,
                "irr_reason": "fallback_opening_date"
            }

    except Exception as e:
        _alog(f"compute_one: ts={ts_code} fallback EX {e}")
        traceback.print_exc()
        # 保底返回
        return {
            "ts_code": ts_code, "date": d,
            "annualized_mwr": None, "flows": len(cfs),
            "used_price_date": used_price_date, "terminal_value": terminal_value,
            "irr_reason": "fallback_error"
        }

def compute_position_xirr_batch(date_yyyymmdd: str, ts_codes: Optional[List[str]] = None) -> List[Dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        if ts_codes:
            codes = ts_codes
        else:
            codes1 = [r["ts_code"] for r in conn.execute("SELECT ts_code FROM position WHERE shares>0").fetchall()]
            codes2 = [r["ts_code"] for r in conn.execute("SELECT DISTINCT ts_code FROM txn").fetchall()]
            codes = sorted(list(set(codes1 + codes2)))

    _alog(f"compute_batch: date={d} codes={len(codes)}")
    out: List[Dict] = []
    for code in codes:
        try:
            out.append(compute_position_xirr(code, date_yyyymmdd))
        except Exception as e:
            _alog(f"compute_batch: ts={code} ERROR {e}")
            traceback.print_exc()
            # 不中断：保留一条错误占位，前端不会用到 annualized_mwr 的 null 以外字段
            out.append({"ts_code": code, "date": d, "annualized_mwr": None, "flows": 0, "error": str(e)})
    _alog(f"compute_batch: done ok={len(out)}")
    return out

def _to_dash_date(s: Optional[str]) -> Optional[str]:
    """把日期字符串规范为 YYYY-MM-DD；支持 YYYY-MM-DD / YYYYMMDD；其它返回 None。"""
    if not s:
        return None
    s = str(s).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    # 再尝试宽松解析
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
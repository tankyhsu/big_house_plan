# backend/services/analytics_svc.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from datetime import datetime, date as dt_date
from math import isfinite

from ..db import get_conn
from ..repository import txn_repo, position_repo, price_repo
from .utils import yyyyMMdd_to_dash

# analytics_svc.py 头部  
from datetime import datetime, date as dt_date
from math import isfinite

def _alog(msg: str):
    # Debug logging disabled for production
    pass

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
        return None

    norm: List[Tuple[str, float]] = []
    for d, a in cashflows:
        dd = _to_dash_date(d)
        if dd is not None:
            norm.append((dd, float(a)))

    if len(norm) < 2:
        return None

    try:
        dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in norm]
    except Exception:
        return None

    t_end: dt_date = max(dates)
    days = [(t_end - d).days / 365.0 for d in dates]
    amounts = [a for _, a in norm]

    r = 0.10
    for _ in range(100):
        try:
            f = sum(a * (1 + r) ** t for a, t in zip(amounts, days))
            df = sum(a * t * (1 + r) ** (t - 1) for a, t in zip(amounts, days))
        except Exception:
            return None
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        if not isfinite(r_new):
            return None
        if r_new < -0.999999:
            r_new = -0.999999
        if abs(r_new - r) < 1e-8:
            return r_new
        r = r_new
    # Algorithm did not converge
    return None

def _build_cashflows_for_ts(ts_code: str, date_dash: str) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[float]]:
    cfs: List[Tuple[str, float]] = []
    used_price_date: Optional[str] = None
    terminal_value: Optional[float] = None

    with get_conn() as conn:
        txns = txn_repo.list_txns_for_code_upto(conn, ts_code, date_dash)

        for t in txns:
            action = (t["action"] or "").upper()
            shares = float(t["shares"] or 0.0)
            price  = None if t["price"] is None else float(t["price"])
            amount = None if t["amount"] is None else float(t["amount"])
            fee    = float(t["fee"] or 0.0)
            d      = t["trade_date"]  # YYYY-MM-DD

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

        pos = position_repo.get_position(conn, ts_code)
        shares_now = float(pos["shares"] or 0.0) if pos else 0.0
        if shares_now > 0:
            last = price_repo.get_last_close_on_or_before(conn, ts_code, date_dash)
            if last is not None:
                used_price_date, price = last[0], last[1]
                terminal_value = shares_now * float(price)
                cfs.append((date_dash, terminal_value))
        # Build cashflows completed
    return cfs, used_price_date, terminal_value


def compute_position_xirr(ts_code: str, date_yyyymmdd: str) -> Dict:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    # Compute XIRR for single position
    cfs, used_price_date, terminal_value = _build_cashflows_for_ts(ts_code, d)
    first_d = cfs[0][0] if cfs else None
    last_d  = cfs[-1][0] if cfs else None
    # Cashflow analysis completed

    # --- 正常路径：有≥2笔现金流，走 XIRR ---
    if len(cfs) >= 2:
        try:
            r = _xirr(cfs)
            # XIRR computation completed
            return {
                "ts_code": ts_code,
                "date": d,
                "annualized_mwr": (float(r) if r is not None else None),
                "flows": len(cfs),
                "used_price_date": used_price_date,
                "terminal_value": terminal_value,
                "irr_reason": "ok" if r is not None else "no_solution"
            }
        except Exception:
            # XIRR computation failed
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
                # No position data for fallback calculation
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
                # Fallback calculation blocked - insufficient data
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
                # No price data available for fallback calculation
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
                # Invalid holding period for fallback calculation
                return {
                    "ts_code": ts_code, "date": d,
                    "annualized_mwr": None, "flows": len(cfs),
                    "used_price_date": used_price_date, "terminal_value": terminal_value,
                    "irr_reason": "invalid_holding_days"
                }

            total_return = (price / avg_cost) - 1.0
            annualized = (1.0 + total_return) ** (365.0 / holding_days) - 1.0

            # Fallback calculation completed successfully
            return {
                "ts_code": ts_code,
                "date": d,
                "annualized_mwr": float(annualized),
                "flows": len(cfs),  # 这里一般为 0 或 1（只有期末市值）
                "used_price_date": used_price_date,
                "terminal_value": terminal_value,
                "irr_reason": "fallback_opening_date"
            }

    except Exception:
        # Fallback calculation failed
        # 保底返回
        return {
            "ts_code": ts_code, "date": d,
            "annualized_mwr": None, "flows": len(cfs),
            "used_price_date": used_price_date, "terminal_value": terminal_value,
            "irr_reason": "fallback_error"
        }

def compute_position_xirr_batch(date_yyyymmdd: str, ts_codes: Optional[List[str]] = None) -> List[Dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    from ..repository.txn_repo import list_txn_codes_distinct
    from ..repository.position_repo import list_position_codes_with_shares
    with get_conn() as conn:
        if ts_codes:
            codes = ts_codes
        else:
            codes1 = list_position_codes_with_shares(conn)
            codes2 = list_txn_codes_distinct(conn)
            codes = sorted(list(set(codes1 + codes2)))

    # 过滤：跳过现金类标的（instrument.type='CASH' 或与配置的 cash_ts_code 相同）
    from .config_svc import get_config
    cfg = get_config()
    cash_code_cfg = (cfg.get("cash_ts_code") or "").upper()
    cash_set = set()
    with get_conn() as conn:
        if codes:
            q = "SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE ts_code IN ({})".format(
                ",".join(["?"]*len(codes))
            )
            for r in conn.execute(q, codes).fetchall():
                t = (r["t"] or "").upper()
                if t == "CASH" or r["ts_code"].upper() == cash_code_cfg:
                    cash_set.add(r["ts_code"])

    # Batch XIRR computation starting
    out: List[Dict] = []
    for code in codes:
        if code in cash_set:
            out.append({
                "ts_code": code,
                "date": d,
                "annualized_mwr": None,
                "flows": 0,
                "irr_reason": "skip_cash"
            })
            continue
        try:
            out.append(compute_position_xirr(code, date_yyyymmdd))
        except Exception as e:
            # Individual position computation failed
            # 不中断：保留一条错误占位，前端不会用到 annualized_mwr 的 null 以外字段
            out.append({"ts_code": code, "date": d, "annualized_mwr": None, "flows": 0, "error": str(e)})
    # Batch computation completed
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

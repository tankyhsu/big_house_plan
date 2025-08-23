# backend/services/analytics_svc.py
from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from datetime import datetime, date as dt_date
from math import isfinite

from ..db import get_conn
from .utils import yyyyMMdd_to_dash

# -------- XIRR 求解（牛顿法 + 守护）---------
def _xirr(cashflows: List[Tuple[str, float]]) -> Optional[float]:
    """
    cashflows: [(YYYY-MM-DD, amount), ...]
      - 买入为负；卖出/分红/期末市值为正
    返回：年化收益率 r（0.123 表示 12.3%），无解返回 None
    """
    if not cashflows or len(cashflows) < 2:
        return None

    # 以期末为基准贴现
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in cashflows]
    t_end: dt_date = max(dates)
    days = [(t_end - d).days / 365.0 for d in dates]
    amounts = [a for _, a in cashflows]

    # 初值：10%
    r = 0.10
    for _ in range(100):
        # f(r) = Σ a_i * (1+r)^ti
        try:
            f = sum(a * (1 + r) ** t for a, t in zip(amounts, days))
            df = sum(a * t * (1 + r) ** (t - 1) for a, t in zip(amounts, days))
        except Exception:
            return None
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        # 简单的边界保护：避免小于 -100%
        if not isfinite(r_new):
            return None
        if r_new < -0.999999:
            r_new = -0.999999
        if abs(r_new - r) < 1e-8:
            return r_new
        r = r_new
    # 收敛失败视为无解
    return None

def _build_cashflows_for_ts(ts_code: str, date_dash: str) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[float]]:
    """
    组装单标的现金流（到 date_dash 为止）：
      - txn: BUY/SELL/DIV/FEE/ADJ -> 现金流
      - 期末：+ shares(date) * 最近可用价（来自 price_eod，≤ date）
    返回：(cashflows, used_price_date, terminal_value)
    """
    cfs: List[Tuple[str, float]] = []
    used_price_date: Optional[str] = None
    terminal_value: Optional[float] = None

    with get_conn() as conn:
        # 1) 交易现金流（到估值日为止）
        txns = conn.execute(
            """
            SELECT date, action, shares, price, amount, fee
            FROM txn
            WHERE ts_code=? AND date<=?
            ORDER BY date ASC, rowid ASC
            """,
            (ts_code, date_dash)
        ).fetchall()

        for t in txns:
            action = (t["action"] or "").upper()
            shares = float(t["shares"] or 0.0)
            price  = None if t["price"] is None else float(t["price"])
            amount = None if t["amount"] is None else float(t["amount"])
            fee    = float(t["fee"] or 0.0)
            d      = t["date"]  # YYYY-MM-DD

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
                # 调整：直接按 amount 的符号入账（正加负减）
                if amount:
                    cfs.append((d, float(amount)))

        # 2) 期末市值：用 position 的当前份额 × 最近可用价（≤ date_dash）
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

        # 3) 若完全没有交易，但 position 有仓位 → 用开仓均价构造“起始现金流”
        if not txns:
            row = conn.execute("SELECT opening_date, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
            if row:
                od = row["opening_date"] or date_dash
                sh = float(row["shares"] or 0.0)
                ac = float(row["avg_cost"] or 0.0)
                if sh > 0 and ac > 0:
                    cfs.insert(0, (od, -(sh * ac)))

    return cfs, used_price_date, terminal_value

def compute_position_xirr(ts_code: str, date_yyyymmdd: str) -> Dict:
    """
    计算单标的自建仓以来资金加权年化收益（XIRR）：
      - 交易现金流：BUY/SELL/DIV/FEE/ADJ
      - 期末市值：position.shares × price_eod(≤date最近价)
      - 无交易但有底仓：用 opening_date & avg_cost 构造初始现金流
    返回：{ ts_code, date, annualized_mwr, flows, used_price_date, terminal_value }
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfs, used_price_date, terminal_value = _build_cashflows_for_ts(ts_code, d)
    r = _xirr(cfs) if len(cfs) >= 2 else None
    return {
        "ts_code": ts_code,
        "date": d,
        "annualized_mwr": (float(r) if r is not None else None),
        "flows": len(cfs),
        "used_price_date": used_price_date,
        "terminal_value": terminal_value
    }

def compute_position_xirr_batch(date_yyyymmdd: str, ts_codes: Optional[List[str]] = None) -> List[Dict]:
    """
    批量计算：默认对所有有持仓（shares>0）或有历史交易的标的计算 XIRR。
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    codes: List[str] = []

    with get_conn() as conn:
        if ts_codes:
            codes = ts_codes
        else:
            # 有持仓的
            codes1 = [r["ts_code"] for r in conn.execute("SELECT ts_code FROM position WHERE shares>0").fetchall()]
            # 或者有交易记录的
            codes2 = [r["ts_code"] for r in conn.execute("SELECT DISTINCT ts_code FROM txn").fetchall()]
            codes = sorted(list(set(codes1 + codes2)))

    out: List[Dict] = []
    for code in codes:
        out.append(compute_position_xirr(code, date_yyyymmdd))
    return out
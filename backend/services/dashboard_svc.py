# backend/services/dashboard_svc.py
import pandas as pd
from ..db import get_conn
from ..repository import reporting_repo
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from datetime import datetime, timedelta
# get_dashboard, list_category, list_position, list_signal 放这里（你已有的“动态口径”实现）

def get_dashboard(date_yyyymmdd: str) -> dict:
    """
    Dashboard KPI 动态口径：
    - 用 position（当前底仓） × price_eod 中 ≤ 指定日的最近可用价 计算市值
    - 成本 = shares × avg_cost
    - ret/pnl 动态计算；signal 仍来自快照（如未calc则可能为0）
    - price_fallback_used: 若某标的在 ≤ 指定日没有任何价格（新标的未同步），视为使用均价回退
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        # 动态聚合：每个标的取 ≤ d 最近价
        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)

        mv = 0.0; cost = 0.0; used_fallback = False
        for r in rows:
            shares = float(r["shares"] or 0.0)
            if shares <= 0: 
                continue
            avg_cost = float(r["avg_cost"] or 0.0)
            eod_close = r["eod_close"]
            if eod_close is None:
                # 没有任何 ≤ d 的价格（新标的/未同步），用均价回退并标记
                used_fallback = True
                price = avg_cost
            else:
                price = float(eod_close)
            mv += shares * price
            cost += shares * avg_cost

        pnl = mv - cost
        ret = (pnl / cost) if cost > 0 else None

        # 当日信号数量来自快照（如果未calc，可能为0）
        sig = conn.execute("SELECT type, COUNT(1) c FROM signal WHERE trade_date=? GROUP BY type", (d,)).fetchall()
        counts = {"stop_gain":0,"overweight":0}
        for r in sig:
            if r["type"] == "STOP_GAIN": counts["stop_gain"] = r["c"]
            if r["type"] == "OVERWEIGHT": counts["overweight"] = r["c"]

    return {
        "date": d,
        "kpi": {"market_value": mv, "cost": cost, "unrealized_pnl": pnl, "ret": ret},
        "signals": {"stop_gain": counts["stop_gain"], "overweight": counts["overweight"]},
        "price_fallback_used": used_fallback
    }

def list_category(date_yyyymmdd: str) -> list[dict]:
    """
    类别分布动态口径（不依赖 portfolio_daily）：
    - 用 position × (≤ 指定日最近价) 动态聚合市值
    - 结合 category.target_units 计算 actual_units / gap_units / overweight
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config()
    unit_amount = float(cfg.get("unit_amount", 3000.0))
    band = float(cfg.get("overweight_band", 0.20))

    with get_conn() as conn:
        # 拉所有类别目标
        cats = pd.read_sql_query("SELECT id AS category_id, name, sub_name, target_units FROM category", conn)

        # 拉标的 + 底仓 + 最近价
        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)
        df = pd.DataFrame([dict(r) for r in rows])
        # 价格回退：无价则用均价（仅用于展示口径）
        df["price"] = df["eod_close"].fillna(df["avg_cost"])
        df["market_value"] = df["shares"] * df["price"]
        df["cost"] = df["shares"] * df["avg_cost"]

        # 按类别聚合
        agg = df.groupby("category_id", as_index=False).agg(
            market_value=("market_value", "sum"),
            cost=("cost", "sum")
        )
        agg["pnl"] = agg["market_value"] - agg["cost"]
        agg["ret"] = agg.apply(lambda r: (r["pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)
        agg = cats.merge(agg, on="category_id", how="left").fillna({"market_value":0.0, "cost":0.0, "pnl":0.0})

        # 份数/越带
        agg["actual_units"] = agg["market_value"] / unit_amount
        agg["gap_units"] = agg["target_units"] - agg["actual_units"]

        def out_of_band(r):
            lower = r["target_units"] * (1 - band); upper = r["target_units"] * (1 + band)
            act = r["actual_units"]
            return 1 if (act < lower or act > upper) else 0

        agg["overweight"] = agg.apply(out_of_band, axis=1)

    # 输出
    out = []
    for _, r in agg.iterrows():
        gap = r["gap_units"]
        out.append({
            "category_id": int(r["category_id"]),
            "name": r["name"], "sub_name": r["sub_name"],
            "target_units": float(r["target_units"]),
            "actual_units": float(r["actual_units"]),
            "gap_units": float(gap),
            "market_value": float(r["market_value"]), "cost": float(r["cost"]),
            "pnl": float(r["pnl"]), "ret": (float(r["ret"]) if r["ret"]==r["ret"] else None),
            "overweight": int(r["overweight"]),
            "suggest_units": round(gap) if gap is not None else None
        })
    return out

def list_position(date_yyyymmdd: str) -> list[dict]:
    """
    标的持仓动态口径：
    - 现价优先用 ≤ 指定日最近价（eod_close）；无则回退到均价
    - 市值/收益率用动态现价计算；snapshot 值仅作兜底
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config(); stop_gain = float(cfg.get("stop_gain_pct", 0.30))
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT pd.*, i.name, i.ts_code, i.category_id, c.name as cat_name, c.sub_name as cat_sub,
               (SELECT close FROM price_eod p 
                 WHERE p.ts_code=i.ts_code AND p.trade_date<=? 
                 ORDER BY p.trade_date DESC LIMIT 1) as eod_close,
               p.shares AS pos_shares, p.avg_cost AS pos_avg_cost
        FROM portfolio_daily pd
        JOIN instrument i ON pd.ts_code=i.ts_code
        JOIN category c ON i.category_id=c.id
        LEFT JOIN position p ON p.ts_code=i.ts_code
        WHERE pd.trade_date=? 
        ORDER BY c.name, c.sub_name, i.ts_code
        """, (d, d)).fetchall()

    out = []
    for r in rows:
        shares = float(r["pos_shares"] or 0.0)
        avg_cost = float(r["pos_avg_cost"] or 0.0)

        if r["eod_close"] is not None:
            close_disp = float(r["eod_close"])
            price_source = "eod"
        else:
            # 没有任何 ≤ d 的价格：回退均价；如 shares=0 则仍为空
            close_disp = avg_cost if shares > 0 else None
            price_source = "avg_cost_fallback" if shares > 0 else "snapshot_close"

        # 动态计算展示口径的市值/收益
        if shares > 0 and close_disp is not None:
            mv_disp = shares * close_disp
            cost_disp = shares * avg_cost
            pnl_disp = mv_disp - cost_disp
            ret_disp = (pnl_disp / cost_disp) if cost_disp > 0 else None
        else:
            # 无持仓或无价，退回快照值（通常为0）
            mv_disp = float(r["market_value"] or 0.0)
            cost_disp = float(r["cost"] or 0.0)
            pnl_disp = float(r["unrealized_pnl"] or (mv_disp - cost_disp))
            ret_disp = r["ret"]

        out.append({
            "cat_name": r["cat_name"], "cat_sub": r["cat_sub"],
            "ts_code": r["ts_code"], "name": r["name"],
            "shares": shares, "avg_cost": avg_cost,
            "close": close_disp, "price_source": price_source,
            "market_value": mv_disp, "cost": cost_disp,
            "unrealized_pnl": pnl_disp, "ret": ret_disp,
            "stop_gain_hit": (ret_disp is not None and stop_gain is not None and ret_disp >= stop_gain)
        })
    return out

def list_signal(date_yyyymmdd: str, typ: str|None) -> list[dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        if typ and typ.upper() != "ALL":
            rows = conn.execute("SELECT * FROM signal WHERE trade_date=? AND type=? ORDER BY level DESC", (d,typ.upper())).fetchall()
        else:
            rows = conn.execute("SELECT * FROM signal WHERE trade_date=? ORDER BY level DESC", (d,)).fetchall()
    return [dict(r) for r in rows]


def _iter_dates(start_dash: str, end_dash: str) -> list[str]:
    d0 = datetime.fromisoformat(start_dash)
    d1 = datetime.fromisoformat(end_dash)
    out = []
    cur = d0
    while cur <= d1:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def aggregate_kpi(start_yyyymmdd: str, end_yyyymmdd: str, period: str = "day") -> list[dict]:
    """
    聚合区间内的 Dashboard KPI：
      - period=day：逐日
      - period=week：每周（ISO 周）末一个点（区间内该周的最后一天）
      - period=month：每月末一个点（区间内该月的最后一天）
    复用动态口径 get_dashboard，避免依赖 snapshot 完整性。
    """
    sd = yyyyMMdd_to_dash(start_yyyymmdd)
    ed = yyyyMMdd_to_dash(end_yyyymmdd)
    days = _iter_dates(sd, ed)

    p = (period or "day").lower()
    if p == "day":
        targets = days
    elif p == "week":
        # 分组到 (ISO 年, ISO 周)，取每组最后一天
        buckets = {}
        for d in days:
            dt = datetime.fromisoformat(d)
            iso = dt.isocalendar()
            key = (iso[0], iso[1])  # (year, week)
            buckets.setdefault(key, []).append(d)
        targets = [v[-1] for _, v in sorted(buckets.items())]
    else:  # month
        buckets = {}
        for d in days:
            dt = datetime.fromisoformat(d)
            key = (dt.year, dt.month)
            buckets.setdefault(key, []).append(d)
        targets = [v[-1] for _, v in sorted(buckets.items())]

    out = []
    for dash_date in targets:
        ymd = dash_date.replace("-", "")
        k = get_dashboard(ymd)
        out.append({
            "date": dash_date,
            "market_value": k["kpi"]["market_value"],
            "cost": k["kpi"]["cost"],
            "unrealized_pnl": k["kpi"]["unrealized_pnl"],
            "ret": k["kpi"]["ret"],
        })
    return out

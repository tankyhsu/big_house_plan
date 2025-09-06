# backend/services/calc_svc.py
import pandas as pd
from ..db import get_conn
from ..logs import LogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from ..repository import portfolio_repo, reporting_repo

# _generate_historical_signals 函数已迁移到 signal_svc.SignalGenerationService

def rebuild_all_historical_signals():
    """重建所有历史信号，现在只包含结构信号和ZIG信号"""
    # 这个函数已不再需要，因为我们移除了止盈止损信号生成逻辑
    # 结构信号和ZIG信号通过其他专门的函数生成
    return {"count": 0, "date_range": "功能已移除 - 不再自动生成止盈止损信号"}

# _generate_historical_signals_for_instrument 函数已迁移到 signal_svc.SignalGenerationService

def calc(date_yyyymmdd: str, log: LogContext):
    """
    执行指定日期的投资组合计算和信号生成
    
    主要功能：
    1. 清除当日已有的投资组合数据，避免重复计算
    2. 计算各标的的市值、成本、未实现盈亏和收益率
    3. 按类别汇总投资组合数据，判断是否超配或缺配
    4. 生成止盈止损信号（避免重复生成已存在的信号）
    
    Args:
        date_yyyymmdd: 计算日期，格式 YYYYMMDD
        log: 日志上下文对象，用于记录计算过程
        
    配置参数说明：
        unit_amount: 单位投资金额，用于计算理论份数
        overweight_band: 超配阈值带，判断是否需要再平衡  
        stop_gain_pct: 止盈阈值百分比
        stop_loss_pct: 止损阈值百分比
        
    业务逻辑：
        - 使用收盘价计算市值，如无收盘价则使用成本价
        - 超配/缺配判断基于实际份数与理论份数的差异
        - 止盈止损信号基于未实现收益率阈值
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config()
    unit_amount = float(cfg.get("unit_amount", 3000))
    band = float(cfg.get("overweight_band", 0.20))
    stop_gain = float(cfg.get("stop_gain_pct", 0.30))
    stop_loss = float(cfg.get("stop_loss_pct", 0.15))  # 止损阈值

    with get_conn() as conn:
        portfolio_repo.clear_day(conn, d)
        conn.commit()

        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)
        df = pd.DataFrame([dict(r) for r in rows])
        # Ensure required columns exist even if empty
        if df.empty:
            df = pd.DataFrame(columns=["ts_code", "category_id", "shares", "avg_cost", "close"])
        else:
            # Align column name with code below
            df.rename(columns={"eod_close": "close"}, inplace=True)
        if "close" in df.columns:
            df["close"] = df["close"].fillna(df["avg_cost"])  # fallback to avg_cost if no price
        df["market_value"] = df["shares"] * df["close"]
        df["cost"] = df["shares"] * df["avg_cost"]
        df["unrealized_pnl"] = df["market_value"] - df["cost"]
        df["ret"] = df.apply(lambda r: (r["unrealized_pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)

        for _, r in df.iterrows():
            portfolio_repo.upsert_portfolio_daily(
                conn,
                d,
                r["ts_code"],
                float(r["market_value"]),
                float(r["cost"]),
                float(r["unrealized_pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                int(r["category_id"]) if r["category_id"] is not None else None,
            )
        conn.commit()

        q2 = """
        SELECT i.category_id, SUM(pd.market_value) mv, SUM(pd.cost) cost
        FROM portfolio_daily pd JOIN instrument i ON pd.ts_code=i.ts_code
        WHERE pd.trade_date=? GROUP BY i.category_id
        """
        cat = pd.read_sql_query(q2, conn, params=(d,))
        m = pd.read_sql_query("SELECT id, target_units FROM category", conn)
        cat = cat.merge(m, left_on="category_id", right_on="id", how="left")

        cat["pnl"] = cat["mv"] - cat["cost"]
        cat["ret"] = cat.apply(lambda r: (r["pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)
        
        # 实时计算份数用于判断overweight，但不存储
        cat["actual_units"] = cat["cost"] / unit_amount
        cat["gap_units"] = cat["target_units"] - cat["actual_units"]
        def out_of_band(r):
            lower = r["target_units"] * (1 - band); upper = r["target_units"] * (1 + band)
            return 1 if (r["actual_units"] < lower or r["actual_units"] > upper) else 0
        cat["overweight"] = cat.apply(out_of_band, axis=1)

        for _, r in cat.iterrows():
            portfolio_repo.upsert_category_daily(
                conn,
                d,
                int(r["category_id"]),
                float(r["mv"]),
                float(r["cost"]),
                float(r["pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                int(r["overweight"]),
            )

        # 使用新的信号生成服务生成当前信号（止盈止损功能已移除）
        from .signal_svc import SignalGenerationService
        SignalGenerationService.generate_current_signals(df, d)
    log.set_payload({"date": date_yyyymmdd})

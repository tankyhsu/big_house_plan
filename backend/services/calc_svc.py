# backend/services/calc_svc.py
import pandas as pd
from ..db import get_conn
from ..logs import LogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from ..repository import portfolio_repo, reporting_repo

def _generate_historical_signals(conn, df, stop_gain, stop_loss):
    """
    为每个持仓标的生成历史信号，找到首次达到止盈/止损条件的正确日期
    """
    for _, r in df.iterrows():
        if r["cost"] <= 0 or not r["ts_code"]:
            continue
            
        ts_code = r["ts_code"]
        avg_cost = float(r["avg_cost"])
        
        # 获取持仓的开仓日期
        opening_date = conn.execute(
            "SELECT opening_date FROM position WHERE ts_code = ?", 
            (ts_code,)
        ).fetchone()
        
        if not opening_date or not opening_date[0]:
            continue
            
        start_date = opening_date[0]
        
        # 获取从开仓日期到今天的历史价格数据
        price_data = conn.execute("""
            SELECT trade_date, close 
            FROM price_eod 
            WHERE ts_code = ? AND trade_date >= ? 
            ORDER BY trade_date ASC
        """, (ts_code, start_date)).fetchall()
        
        if not price_data:
            continue
            
        # 检查每个历史日期是否首次达到条件
        for trade_date, close_price in price_data:
            if not close_price:
                continue
                
            # 计算收益率
            ret = (close_price - avg_cost) / avg_cost
            
            # 检查止盈条件
            if ret >= stop_gain:
                # 检查是否已经存在该信号
                existing = conn.execute(
                    "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
                    (trade_date, ts_code, "STOP_GAIN")
                ).fetchone()
                
                if not existing:
                    portfolio_repo.insert_signal_instrument(
                        conn,
                        trade_date,
                        ts_code,
                        "HIGH",
                        "STOP_GAIN",
                        f"{ts_code} 收益率 {ret:.2%} 达到止盈目标 {stop_gain:.0%}",
                    )
                    # 找到首次触发就停止检查后续日期的止盈
                    break
                    
            # 检查止损条件
            elif ret <= -stop_loss:
                # 检查是否已经存在该信号
                existing = conn.execute(
                    "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
                    (trade_date, ts_code, "STOP_LOSS")
                ).fetchone()
                
                if not existing:
                    portfolio_repo.insert_signal_instrument(
                        conn,
                        trade_date,
                        ts_code,
                        "HIGH",
                        "STOP_LOSS",
                        f"{ts_code} 收益率 {ret:.2%} 触发止损阈值 -{stop_loss:.0%}",
                    )
                    # 找到首次触发就停止检查后续日期的止损
                    break

def rebuild_all_historical_signals():
    """
    重建所有历史信号：
    1. 清除现有的自动信号（保留手动信号）
    2. 重新生成完整的历史信号
    """
    cfg = get_config()
    stop_gain = float(cfg.get("stop_gain_pct", 0.30))
    stop_loss = float(cfg.get("stop_loss_pct", 0.15))
    
    with get_conn() as conn:
        # 1. 清除现有的自动信号，保留手动信号
        conn.execute("DELETE FROM signal WHERE type IN ('STOP_GAIN', 'STOP_LOSS')")
        conn.commit()
        
        # 2. 获取所有有持仓的标的
        rows = conn.execute("""
            SELECT p.ts_code, p.shares, p.avg_cost, p.opening_date
            FROM position p 
            WHERE p.shares > 0 AND p.opening_date IS NOT NULL
        """).fetchall()
        
        df = pd.DataFrame([dict(r) for r in rows], columns=["ts_code", "shares", "avg_cost", "opening_date"])
        
        if df.empty:
            return {"count": 0, "date_range": "无数据"}
        
        # 3. 生成历史信号
        signal_count = 0
        min_date = None
        max_date = None
        
        for _, r in df.iterrows():
            count, dates = _generate_historical_signals_for_instrument(
                conn, r["ts_code"], float(r["avg_cost"]), r["opening_date"], stop_gain, stop_loss
            )
            signal_count += count
            if dates:
                if min_date is None or dates[0] < min_date:
                    min_date = dates[0]
                if max_date is None or dates[1] > max_date:
                    max_date = dates[1]
        
        conn.commit()
        
        date_range = f"{min_date} 至 {max_date}" if min_date and max_date else "无信号"
        return {"count": signal_count, "date_range": date_range}

def _generate_historical_signals_for_instrument(conn, ts_code, avg_cost, opening_date, stop_gain, stop_loss):
    """
    为单个标的生成历史信号，返回信号数量和日期范围
    """
    # 获取从开仓日期到今天的历史价格数据
    price_data = conn.execute("""
        SELECT trade_date, close 
        FROM price_eod 
        WHERE ts_code = ? AND trade_date >= ? 
        ORDER BY trade_date ASC
    """, (ts_code, opening_date)).fetchall()
    
    if not price_data:
        return 0, None
    
    signal_count = 0
    first_signal_date = None
    last_signal_date = None
    
    # 检查每个历史日期是否首次达到条件
    for trade_date, close_price in price_data:
        if not close_price:
            continue
            
        # 计算收益率
        ret = (close_price - avg_cost) / avg_cost
        
        # 检查止盈条件
        if ret >= stop_gain:
            # 检查是否已经存在该信号
            existing = conn.execute(
                "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
                (trade_date, ts_code, "STOP_GAIN")
            ).fetchone()
            
            if not existing:
                portfolio_repo.insert_signal_instrument(
                    conn,
                    trade_date,
                    ts_code,
                    "HIGH",
                    "STOP_GAIN",
                    f"{ts_code} 收益率 {ret:.2%} 达到止盈目标 {stop_gain:.0%}",
                )
                signal_count += 1
                if first_signal_date is None:
                    first_signal_date = trade_date
                last_signal_date = trade_date
                # 找到首次触发就停止检查后续日期的止盈
                break
                
        # 检查止损条件
        elif ret <= -stop_loss:
            # 检查是否已经存在该信号
            existing = conn.execute(
                "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
                (trade_date, ts_code, "STOP_LOSS")
            ).fetchone()
            
            if not existing:
                portfolio_repo.insert_signal_instrument(
                    conn,
                    trade_date,
                    ts_code,
                    "HIGH",
                    "STOP_LOSS",
                    f"{ts_code} 收益率 {ret:.2%} 触发止损阈值 -{stop_loss:.0%}",
                )
                signal_count += 1
                if first_signal_date is None:
                    first_signal_date = trade_date
                last_signal_date = trade_date
                # 找到首次触发就停止检查后续日期的止损
                break
    
    if first_signal_date and last_signal_date:
        return signal_count, (first_signal_date, last_signal_date)
    return signal_count, None

def calc(date_yyyymmdd: str, log: LogContext):
    print("触发计算逻辑")
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

        # 只生成今日信号（快照功能），但需要检查历史信号避免重复
        for _, r in df.iterrows():
            if r["cost"] > 0:
                ret = r["unrealized_pnl"] / r["cost"]
                ts_code = r["ts_code"]
                
                if ret is not None and ret >= stop_gain:
                    # 检查该标的是否已经有过STOP_GAIN信号（历史任意日期）
                    existing_gain = conn.execute(
                        "SELECT id FROM signal WHERE ts_code=? AND type=?",
                        (ts_code, "STOP_GAIN")
                    ).fetchone()
                    
                    if not existing_gain:
                        portfolio_repo.insert_signal_instrument(
                            conn,
                            d,
                            ts_code,
                            "HIGH",  # 止盈信号设为高优先级
                            "STOP_GAIN",
                            f"{ts_code} 收益率 {ret:.2%} 达到止盈目标 {stop_gain:.0%}",
                        )
                        
                elif ret is not None and ret <= -stop_loss:
                    # 检查该标的是否已经有过STOP_LOSS信号（历史任意日期）
                    existing_loss = conn.execute(
                        "SELECT id FROM signal WHERE ts_code=? AND type=?",
                        (ts_code, "STOP_LOSS")
                    ).fetchone()
                    
                    if not existing_loss:
                        portfolio_repo.insert_signal_instrument(
                            conn,
                            d,
                            ts_code,
                            "HIGH",  # 止损信号设为高优先级
                            "STOP_LOSS",
                            f"{ts_code} 收益率 {ret:.2%} 触发止损阈值 -{stop_loss:.0%}",
                        )
        conn.commit()
    log.set_payload({"date": date_yyyymmdd})

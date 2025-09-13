from __future__ import annotations

# backend/services/calc_svc.py
import pandas as pd
from ..db import get_conn
from ..logs import OperationLogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from ..repository import reporting_repo

# _generate_historical_signals 函数已迁移到 signal_svc.SignalGenerationService

def rebuild_all_historical_signals():
    """重建所有历史信号，现在只包含结构信号和ZIG信号"""
    # 这个函数已不再需要，因为我们移除了止盈止损信号生成逻辑
    # 结构信号和ZIG信号通过其他专门的函数生成
    return {"count": 0, "date_range": "功能已移除 - 不再自动生成止盈止损信号"}

# _generate_historical_signals_for_instrument 函数已迁移到 signal_svc.SignalGenerationService

def calc(date_yyyymmdd: str, log: OperationLogContext):
    """
    执行指定日期的信号生成
    
    主要功能：
    1. 获取当前持仓数据和价格数据
    2. 生成交易信号（通过SignalGenerationService）
    
    注意：不再维护portfolio_daily和category_daily表，
    所有实时数据通过position表和price_eod表动态计算获得
    
    Args:
        date_yyyymmdd: 计算日期，格式 YYYYMMDD
        log: 日志上下文对象，用于记录计算过程
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)

    with get_conn() as conn:
        # 获取活跃标的的持仓和价格数据用于信号生成
        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)
        df = pd.DataFrame([dict(r) for r in rows])
        
        # 确保必要列存在（即使为空）
        if df.empty:
            df = pd.DataFrame(columns=["ts_code", "category_id", "shares", "avg_cost", "close"])
        else:
            # 统一列名
            df.rename(columns={"eod_close": "close"}, inplace=True)
        
        # 价格回退处理：无价格则使用成本价
        if "close" in df.columns:
            df["close"] = df["close"].fillna(df["avg_cost"])
        
        # 计算基本指标用于信号生成
        df["market_value"] = df["shares"] * df["close"]
        df["cost"] = df["shares"] * df["avg_cost"]
        df["unrealized_pnl"] = df["market_value"] - df["cost"]
        df["ret"] = df.apply(lambda r: (r["unrealized_pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)

        # 生成交易信号
        from .signal_svc import SignalGenerationService
        SignalGenerationService.generate_current_signals(df, d)
        
    log.set_payload({"date": date_yyyymmdd})

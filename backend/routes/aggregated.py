"""
聚合API路由 - 提供页面级别的数据聚合接口
减少前端API调用次数，提高性能
"""
from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.aggregator_svc import aggregator_service, DataRequest

router = APIRouter()


class FlexibleDataRequest(BaseModel):
    """灵活的数据请求模型"""
    include_dashboard: bool = False
    include_categories: bool = False
    include_positions: bool = False
    include_signals: bool = False
    include_watchlist: bool = False
    include_transactions: bool = False
    include_instruments: bool = False
    include_settings: bool = False
    include_monthly_stats: bool = False

    # 参数配置
    date: Optional[str] = None
    signal_start_date: Optional[str] = None
    signal_end_date: Optional[str] = None
    signal_limit: int = 100
    signal_ts_code: Optional[str] = None
    signal_type: Optional[str] = None

    txn_page: int = 1
    txn_size: int = 20

    position_include_zero: bool = True
    position_with_price: bool = True


@router.get("/api/aggregated/dashboard")
def api_dashboard_full(date: str = Query(None, pattern=r"^\d{8}$")):
    """
    Dashboard页面完整数据聚合
    包含: dashboard, categories, positions, signals
    """
    try:
        result = aggregator_service.fetch_dashboard_full(date)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/aggregated/watchlist")
def api_watchlist_full(date: str = Query(None, pattern=r"^\d{8}$")):
    """
    Watchlist页面完整数据聚合
    包含: watchlist, instruments, categories_list, signals_batch
    """
    try:
        result = aggregator_service.fetch_watchlist_full(date)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/aggregated/transactions")
def api_transactions_page(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    """
    Transaction页面完整数据聚合
    包含: transactions, monthly_stats, instruments, categories_list, positions_raw, settings
    """
    try:
        result = aggregator_service.fetch_transaction_page(page, size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/aggregated/flexible")
def api_flexible_data(request: FlexibleDataRequest):
    """
    灵活的数据聚合接口
    客户端可以按需指定需要的数据类型，避免过度获取
    """
    try:
        # 构建信号参数
        signal_params = None
        if request.include_signals:
            signal_params = {
                "start_date": request.signal_start_date,
                "end_date": request.signal_end_date,
                "limit": request.signal_limit,
                "ts_code": request.signal_ts_code,
                "type": request.signal_type
            }
            # 移除None值
            signal_params = {k: v for k, v in signal_params.items() if v is not None}

        # 构建交易参数
        txn_params = None
        if request.include_transactions:
            txn_params = {
                "page": request.txn_page,
                "size": request.txn_size
            }

        # 构建持仓参数
        position_params = None
        if request.include_positions:
            position_params = {
                "include_zero": request.position_include_zero,
                "with_price": request.position_with_price,
                "date": request.date
            }

        # 构建请求对象
        data_request = DataRequest(
            include_dashboard=request.include_dashboard,
            include_categories=request.include_categories,
            include_positions=request.include_positions,
            include_signals=request.include_signals,
            include_watchlist=request.include_watchlist,
            include_transactions=request.include_transactions,
            include_instruments=request.include_instruments,
            include_settings=request.include_settings,
            include_monthly_stats=request.include_monthly_stats,
            date=request.date,
            signal_params=signal_params,
            txn_params=txn_params,
            position_params=position_params
        )

        result = aggregator_service.fetch_data(data_request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/aggregated/review")
def api_review_page(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    ts_codes: Optional[str] = Query(None, description="逗号分隔的标的代码")
):
    """
    Review页面数据聚合
    包含: dashboard_aggregate, signals, position_series, txn_range等
    """
    try:
        from ..services.dashboard_svc import aggregate_kpi, get_position_series
        from ..routes.transactions import api_txn_range
        from datetime import datetime

        # 格式化日期
        start_date = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        end_date = f"{end[:4]}-{end[4:6]}-{end[6:8]}"

        result = {
            "_meta": {
                "start": start,
                "end": end,
                "start_date": start_date,
                "end_date": end_date
            }
        }

        # Dashboard聚合数据
        result["dashboard_aggregate"] = {
            "period": "week",
            "start": start,
            "end": end,
            "items": aggregate_kpi(start, end, "week")
        }

        # 信号数据
        signal_params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": 1000
        }
        if ts_codes:
            codes_list = [c.strip() for c in ts_codes.split(",") if c.strip()]
            if codes_list:
                # 如果指定了标的，获取每个标的的信号
                result["signals"] = {}
                for code in codes_list:
                    params = signal_params.copy()
                    params["ts_code"] = code
                    result["signals"][code] = aggregator_service.fetcher.get_signals_data(params)
        else:
            result["signals"] = aggregator_service.fetcher.get_signals_data(signal_params)

        # 原始持仓数据
        result["positions_raw"] = aggregator_service.fetcher.get_positions_raw_data(
            include_zero=False
        )

        # 如果指定了标的，获取持仓序列和交易数据
        if ts_codes:
            codes = [c.strip() for c in ts_codes.split(",") if c.strip()]
            if codes:
                # 持仓序列数据
                result["position_series"] = {
                    "items": get_position_series(start, end, codes)
                }

                # 交易范围数据
                from ..routes.transactions import api_txn_range
                import sqlite3
                from ..db import get_conn

                # 直接查询交易数据而不调用API路由
                try:
                    sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
                    ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"

                    base_sql = (
                        "SELECT t.trade_date AS date, t.ts_code, i.name AS name, t.action, t.shares, t.price, t.amount, t.fee "
                        "FROM txn t LEFT JOIN instrument i ON i.ts_code = t.ts_code "
                        "WHERE t.trade_date >= ? AND t.trade_date <= ?"
                    )
                    params = [sd, ed]

                    if codes:
                        placeholders = ",".join(["?"] * len(codes))
                        base_sql += f" AND t.ts_code IN ({placeholders})"
                        params.extend(codes)
                    base_sql += " ORDER BY t.trade_date ASC, t.id ASC"

                    with get_conn() as conn:
                        rows = conn.execute(base_sql, params).fetchall()
                        from ..domain.txn_engine import round_price, round_quantity, round_shares, round_amount
                        items = [
                            {
                                "date": r["date"],
                                "ts_code": r["ts_code"],
                                "name": r["name"],
                                "action": r["action"],
                                "shares": round_shares(float(r["shares"] or 0.0)),
                                "price": (round_price(float(r["price"])) if r["price"] is not None else None),
                                "amount": (round_amount(float(r["amount"])) if r["amount"] is not None else None),
                                "fee": (round_amount(float(r["fee"])) if r["fee"] is not None else None),
                            }
                            for r in rows
                        ]
                    result["transactions_range"] = {"items": items}
                except Exception as e:
                    result["transactions_range"] = {"items": [], "error": str(e)}

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
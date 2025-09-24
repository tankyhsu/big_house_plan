from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException, Query
import warnings

from ..services.dashboard_svc import (
    get_dashboard,
    list_category,
    list_position,
    list_signal,
    list_signal_all,
    aggregate_kpi,
)

router = APIRouter()

@router.get("/api/dashboard", deprecated=True)
def api_dashboard(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    ⚠️ DEPRECATED: Use /api/aggregated/dashboard instead.
    This endpoint will be removed in a future version.
    """
    warnings.warn(
        "API /api/dashboard is deprecated. Use /api/aggregated/dashboard instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_dashboard(date)

@router.get("/api/dashboard/aggregate")
def api_dashboard_aggregate(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    period: Literal["day", "week", "month"] = Query("day"),
):
    try:
        items = aggregate_kpi(start, end, period)
        return {"period": period, "start": start, "end": end, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/category", deprecated=True)
def api_category(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    ⚠️ DEPRECATED: Use /api/aggregated/dashboard instead.
    This endpoint will be removed in a future version.
    """
    warnings.warn(
        "API /api/category is deprecated. Use /api/aggregated/dashboard instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return list_category(date)

@router.get("/api/position", deprecated=True)
def api_position(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    ⚠️ DEPRECATED: Use /api/aggregated/dashboard instead.
    This endpoint will be removed in a future version.
    """
    warnings.warn(
        "API /api/position is deprecated. Use /api/aggregated/dashboard instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return list_position(date)

@router.get("/api/signal")
def api_signal(
    date: str = Query(..., pattern=r"^\d{8}$"),
    type: str | None = Query(None),
    ts_code: str | None = Query(None),
):
    return list_signal(date, type, ts_code)

@router.get("/api/signal/all")
def api_signal_all(
    type: str | None = Query(None),
    ts_code: str | None = Query(None),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000),
):
    return list_signal_all(type, ts_code, start_date, end_date, limit)

@router.get("/api/series/position")
def api_position_series(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    ts_codes: str = Query(..., description="Comma-separated ts_codes"),
):
    try:
        from ..services.dashboard_svc import get_position_series
        codes = [code.strip() for code in ts_codes.split(",") if code.strip()]
        items = get_position_series(start, end, codes)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


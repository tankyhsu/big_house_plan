from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query

from ..services.dashboard_svc import (
    get_dashboard,
    list_category,
    list_position,
    list_signal,
    list_signal_all,
    aggregate_kpi,
)

router = APIRouter()

@router.get("/api/dashboard")
def api_dashboard(date: str = Query(..., pattern=r"^\d{8}$")):
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

@router.get("/api/category")
def api_category(date: str = Query(..., pattern=r"^\d{8}$")):
    return list_category(date)

@router.get("/api/position")
def api_position(date: str = Query(..., pattern=r"^\d{8}$")):
    return list_position(date)

@router.get("/api/signal")
def api_signal(
    date: str = Query(..., pattern=r"^\d{8}$"),
    type: Optional[str] = Query(None),
    ts_code: Optional[str] = Query(None),
):
    return list_signal(date, type, ts_code)

@router.get("/api/signal/all")
def api_signal_all(
    type: Optional[str] = Query(None),
    ts_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000),
):
    return list_signal_all(type, ts_code, start_date, end_date, limit)


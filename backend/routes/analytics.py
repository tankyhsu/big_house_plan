from fastapi import APIRouter, HTTPException, Query

from ..services.analytics_svc import compute_position_xirr, compute_position_xirr_batch

router = APIRouter()


@router.get("/api/position/irr")
def api_position_irr(ts_code: str = Query(...), date: str = Query(..., pattern=r"^\d{8}$")):
    try:
        return compute_position_xirr(ts_code, date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/position/irr/batch")
def api_position_irr_batch(date: str = Query(..., pattern=r"^\d{8}$")):
    try:
        return compute_position_xirr_batch(date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
import warnings

from ..services.watchlist_svc import list_watchlist, add_to_watchlist, remove_from_watchlist

router = APIRouter()


class WatchlistAdd(BaseModel):
    ts_code: str
    note: str | None = None


@router.get("/api/watchlist", deprecated=True)
def api_watchlist(date: str | None = Query(None, pattern=r"^\d{8}$")):
    """
    ⚠️ DEPRECATED: Use /api/aggregated/watchlist instead.
    This endpoint will be removed in a future version.
    """
    warnings.warn(
        "API /api/watchlist is deprecated. Use /api/aggregated/watchlist instead.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        items = list_watchlist(with_last_price=True, on_date_yyyymmdd=date)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/watchlist/add")
def api_watchlist_add(body: WatchlistAdd):
    try:
        add_to_watchlist(body.ts_code, body.note)
        return {"message": "ok"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/watchlist/remove")
def api_watchlist_remove(ts_code: str = Body(..., embed=True)):
    try:
        remove_from_watchlist(ts_code)
        return {"message": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


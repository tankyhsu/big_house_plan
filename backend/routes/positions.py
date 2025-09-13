from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logs import OperationLogContext
from ..services.position_svc import (
    list_positions_raw,
    set_opening_position,
    update_position_one,
    delete_position,
)
from ..services.calc_svc import calc

router = APIRouter()


class OpeningPos(BaseModel):
    ts_code: str
    shares: float
    avg_cost: float
    date: str  # YYYY-MM-DD


class PositionUpdateBody(BaseModel):
    ts_code: str
    shares: float | None = None
    avg_cost: float | None = None
    date: str  # YYYY-MM-DD
    opening_date: str | None = None


@router.get("/api/position/raw")
def api_position_raw(include_zero: bool = True):
    return list_positions_raw(include_zero=include_zero)


@router.post("/api/position/set_opening")
def api_set_opening_position(body: OpeningPos):
    log = OperationLogContext("SET_OPENING_POSITION")
    log.set_payload(body.dict())
    try:
        after = set_opening_position(body.ts_code, body.shares, body.avg_cost, body.date, log)
        date_yyyymmdd = body.date.replace("-", "")
        calc(date_yyyymmdd, OperationLogContext("CALC_AFTER_OPENING"))
        log.write("OK")
        return {"message": "ok", "position": after}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/position/update")
def api_position_update(body: PositionUpdateBody):
    log = OperationLogContext("UPDATE_POSITION")
    log.set_payload(body.dict())
    try:
        out = update_position_one(
            body.ts_code, body.shares, body.avg_cost, body.date, body.opening_date
        )
        calc(body.date.replace("-", ""), OperationLogContext("CALC_AFTER_POSITION_UPDATE"))
        log.write("OK")
        return {"message": "ok", "position": out}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/position/delete")
def api_position_delete(ts_code: str):
    log = OperationLogContext("DELETE_POSITION")
    log.set_payload({"ts_code": ts_code})
    try:
        delete_position(ts_code, log)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


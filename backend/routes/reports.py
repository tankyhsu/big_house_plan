from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from ..logs import OperationLogContext
from ..services.calc_svc import calc

router = APIRouter()


class DateBody(BaseModel):
    date: str | None = None


@router.post("/api/calc")
def api_calc(body: DateBody):
    log = OperationLogContext("CALC")
    log.set_payload(body.model_dump())
    try:
        calc(body.date, log)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/report/export")
def api_export(body: DateBody = Body(default=DateBody())):
    log = OperationLogContext("EXPORT_REPORT")
    log.set_payload(body.model_dump())
    log.write("OK")
    d = body.date or "today"
    return {
        "message": "ok",
        "files": [
            f"exports/category_{d}.csv",
            f"exports/instrument_{d}.csv",
            f"exports/signals_{d}.csv",
        ],
    }


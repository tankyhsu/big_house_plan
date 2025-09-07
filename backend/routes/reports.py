from fastapi import APIRouter, Body
from pydantic import BaseModel
from ..logs import LogContext

router = APIRouter()


class DateBody(BaseModel):
    date: str | None = None


@router.post("/api/report/export")
def api_export(body: DateBody = Body(default=DateBody())):
    log = LogContext("EXPORT_REPORT")
    log.set_payload(body.dict())
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


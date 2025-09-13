from __future__ import annotations

from fastapi import APIRouter

from ..logs import search_operation_logs

router = APIRouter()


@router.get("/api/logs/search")
def api_logs_search(
    page: int = 1,
    size: int = 20,
    action: str | None = None,
    query: str | None = None,
    ts_from: str | None = None,
    ts_to: str | None = None,
):
    total, items = search_operation_logs(query, action, ts_from, ts_to, page, size)
    return {"total": total, "items": items}


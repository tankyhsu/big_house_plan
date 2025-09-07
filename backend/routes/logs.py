from typing import Optional
from fastapi import APIRouter

from ..logs import search_logs

router = APIRouter()


@router.get("/api/logs/search")
def api_logs_search(
    page: int = 1,
    size: int = 20,
    action: Optional[str] = None,
    query: Optional[str] = None,
    ts_from: Optional[str] = None,
    ts_to: Optional[str] = None,
):
    total, items = search_logs(query, action, ts_from, ts_to, page, size)
    return {"total": total, "items": items}


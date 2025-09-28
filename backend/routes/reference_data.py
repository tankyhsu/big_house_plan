from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from ..logs import OperationLogContext
from ..db import get_conn
from ..services.calc_svc import calc
from ..services.category_svc import (
    create_category,
    list_categories,
    update_category as svc_update_category,
)
from ..services.instrument_svc import (
    create_instrument,
    list_instruments,
    seed_load,
    get_instrument_detail,
    edit_instrument,
)
from ..services.fund_svc import fetch_fund_profile
from ..repository.instrument_repo import set_active as repo_set_active

router = APIRouter()


class CategoryCreate(BaseModel):
    name: str
    sub_name: str = ""
    target_units: float


class CategoryUpdateItem(BaseModel):
    id: int
    sub_name: str | None = None
    target_units: float | None = None


class CategoryBulkUpdate(BaseModel):
    items: list[CategoryUpdateItem]


class InstrumentCreate(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True
    type: str | None = None


class InstrumentUpdate(BaseModel):
    ts_code: str
    active: bool
    type: str | None = None


class InstrumentEdit(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True
    type: str | None = None


@router.get("/api/category/list")
def api_category_list():
    return list_categories()


@router.post("/api/category/create")
def api_category_create(body: CategoryCreate):
    log = OperationLogContext("CREATE_CATEGORY")
    log.set_payload(body.dict())
    try:
        new_id = create_category(body.name, body.sub_name, body.target_units, log)
        log.write("OK")
        return {"message": "ok", "id": new_id}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/category/update")
def api_category_update(body: CategoryUpdateItem):
    log = OperationLogContext("UPDATE_CATEGORY")
    log.set_payload(body.dict())
    try:
        svc_update_category(body.id, body.sub_name, body.target_units, log)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/category/bulk-update")
def api_category_bulk_update(body: CategoryBulkUpdate):
    log = OperationLogContext("BULK_UPDATE_CATEGORY")
    log.set_payload({"count": len(body.items)})
    try:
        for item in body.items:
            svc_update_category(item.id, item.sub_name, item.target_units, log)
        log.write("OK")
        return {"message": "ok", "updated": len(body.items)}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/instrument/list")
def api_instrument_list():
    return list_instruments()


@router.get("/api/instrument/get")
def api_instrument_get(ts_code: str = Query(...)):
    try:
        return get_instrument_detail(ts_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fund/profile")
def api_fund_profile(ts_code: str = Query(...)):
    """Get fund profile including holdings, scale, and managers data."""
    try:
        # First check if instrument exists and is a fund
        instrument = get_instrument_detail(ts_code)
        if not instrument:
            raise HTTPException(status_code=404, detail="Instrument not found")

        if instrument.get("type") != "FUND":
            raise HTTPException(status_code=404, detail="Not a fund instrument")

        profile = fetch_fund_profile(ts_code)
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/instrument/create")
def api_instrument_create(body: InstrumentCreate, recalc_today: bool = Query(False)):
    log = OperationLogContext("CREATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        create_instrument(
            body.ts_code,
            body.name,
            body.category_id,
            body.active,
            log,
            sec_type=body.type,
        )
        if recalc_today:
            from datetime import datetime

            today = datetime.now().strftime("%Y%m%d")
            calc(today, OperationLogContext("CALC_AFTER_INSTRUMENT_CREATE"))
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/instrument/update")
def api_instrument_update(body: InstrumentUpdate):
    log = OperationLogContext("UPDATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        with get_conn() as conn:
            repo_set_active(conn, body.ts_code, body.active)
            conn.commit()
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/instrument/edit")
def api_instrument_edit(body: InstrumentEdit):
    log = OperationLogContext("EDIT_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        edit_instrument(
            body.ts_code,
            body.name,
            int(body.category_id),
            bool(body.active),
            body.type,
            log,
        )
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/seed/load")
def api_seed_load_route(
    categories_csv: str = Body(...),
    instruments_csv: str = Body(...),
    recalc_today: bool = Query(False),
):
    log = OperationLogContext("SEED_LOAD")
    log.set_payload({"categories_csv": categories_csv, "instruments_csv": instruments_csv})
    try:
        res = seed_load(categories_csv, instruments_csv, log)
        if recalc_today:
            from datetime import datetime

            today = datetime.now().strftime("%Y%m%d")
            calc(today, OperationLogContext("CALC_AFTER_SEED_LOAD"))
        log.write("OK")
        return {"message": "ok", **res}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


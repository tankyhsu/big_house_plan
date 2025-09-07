from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logs import LogContext
from ..services.config_svc import get_config, update_config

router = APIRouter()


@router.get("/api/settings/get")
def api_settings_get():
    cfg = get_config()
    fields = [
        "unit_amount",
        "stop_gain_pct",
        "stop_loss_pct",
        "overweight_band",
        "ma_short",
        "ma_long",
        "ma_risk",
        "tushare_token",
    ]
    out = {k: v for k, v in cfg.items() if k in fields}
    if out.get("tushare_token"):
        out["tushare_token"] = "***masked***"
    return out


class SettingsUpdateBody(BaseModel):
    updates: dict


@router.post("/api/settings/update")
def api_settings_update(body: SettingsUpdateBody):
    log = LogContext("SETTINGS_UPDATE")
    log.set_payload(body.dict())
    try:
        updated_keys = update_config(body.updates, log)
        log.write("OK")
        return {"message": "ok", "updated": updated_keys}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))


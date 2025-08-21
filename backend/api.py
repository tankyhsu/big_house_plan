from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional, Literal
from .logs import ensure_log_schema, LogContext, search_logs
# ... 现有 imports ...
from .services import (
    get_dashboard, list_category, list_position, list_signal,
    list_txn, create_txn, update_config, get_config, calc,
    create_category, create_instrument, set_opening_position,
    seed_load, bulk_txn,
    list_positions_raw, update_position_one,
    list_instruments, list_categories  # <== 新增
)

from .db import get_conn

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="portfolio-ui-api", version="0.1.0")

# 允许前端开发端口访问；如有其它端口，也加上
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],   # 覆盖 OPTIONS/POST/GET/DELETE...
    allow_headers=["*"],   # 允许自定义头，如 Content-Type、Authorization
)
@app.on_event("startup")
def on_startup():
    ensure_log_schema()

# ===== 基础健康检查 =====
@app.get("/health")
def health():
    """健康检查接口，用于确认 API 服务是否正常运行"""
    return {"status":"ok"}

@app.get("/version")
def version():
    """返回 API 服务的版本信息"""
    return {"app":"portfolio-ui-api","version":"0.1.0"}

# ===== Dashboard/Views =====
@app.get("/api/dashboard")
def api_dashboard(date: str = Query(..., pattern=r"^\d{8}$")):
    """获取指定日期的组合总览（总市值、成本、收益、信号统计等）"""
    return get_dashboard(date)

@app.get("/api/category")
def api_category(date: str = Query(..., pattern=r"^\d{8}$")):
    """获取指定日期的各类别汇总信息（市值、成本、收益、目标/实际份额、配比偏离等）"""
    return list_category(date)

@app.get("/api/position")
def api_position(date: str = Query(..., pattern=r"^\d{8}$")):
    """获取指定日期的标的持仓明细（数量、均价、现价、收益、止盈信号等）"""
    return list_position(date)

@app.get("/api/signal")
def api_signal(date: str = Query(..., pattern=r"^\d{8}$"), type: Optional[str] = Query(None)):
    """获取指定日期触发的信号（止盈、配比越带等）"""
    return list_signal(date, type)

# ===== Txn（交易相关接口） =====
class TxnCreate(BaseModel):
    ts_code: str
    date: str  # YYYY-MM-DD
    action: Literal["BUY","SELL","DIV","FEE","ADJ"]
    shares: float
    price: Optional[float] = None
    amount: Optional[float] = None
    fee: Optional[float] = None
    notes: Optional[str] = None

@app.get("/api/txn/list")
def api_txn_list(page: int = 1, size: int = 20):
    """分页查询历史交易流水（BUY/SELL/DIV/FEE/ADJ）"""
    total, items = list_txn(page, size)
    return {"total": total, "items": items}

@app.post("/api/txn/create", status_code=201)
def api_txn_create(body: TxnCreate):
    """新增一笔交易，并自动更新 position（持仓均价和数量）"""
    log = LogContext("CREATE_TXN")
    log.set_payload(body.dict())
    try:
        res = create_txn(body.dict(), log)
        log.write("OK")
        return {"message":"ok","position":res}
    except ValueError as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail="internal error")

# ===== Calc/Sync/Report =====
class DateBody(BaseModel):
    date: Optional[str] = None  # YYYYMMDD

@app.post("/api/calc")
def api_calc(body: DateBody = Body(default=DateBody())):
    """对指定日期进行快照计算，更新 portfolio_daily / category_daily / signal"""
    import datetime as dt
    date = body.date or dt.datetime.now().strftime("%Y%m%d")
    log = LogContext("CALC_SNAPSHOT")
    try:
        calc(date, log)
        log.write("OK")
        return {"message":"ok","date": f"{date[0:4]}-{date[4:6]}-{date[6:8]}"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-prices")
def api_sync_prices(body: DateBody = Body(default=DateBody())):
    """同步指定日期的收盘价（当前为占位，后续接入 TuShare 获取真实价格）"""
    log = LogContext("SYNC_PRICES")
    log.set_payload(body.dict())
    log.write("OK")
    return {"message":"ok","date": (body.date or None)}

@app.post("/api/report/export")
def api_export(body: DateBody = Body(default=DateBody())):
    """导出指定日期的报表（当前为占位，返回文件路径列表）"""
    log = LogContext("EXPORT_REPORT")
    log.set_payload(body.dict())
    log.write("OK")
    d = body.date or "today"
    return {"message":"ok","files":[f"exports/category_{d}.csv", f"exports/instrument_{d}.csv", f"exports/signals_{d}.csv"]}

# ===== Settings（配置相关接口） =====
class SettingsUpdate(BaseModel):
    unit_amount: Optional[float] = None
    stop_gain_pct: Optional[float] = None
    overweight_band: Optional[float] = None
    ma_short: Optional[int] = None
    ma_long: Optional[int] = None
    ma_risk: Optional[int] = None
    tushare_token: Optional[str] = None

@app.get("/api/settings/get")
def api_settings_get():
    """获取当前系统配置（unit_amount, 止盈阈值, 配比带宽等）"""
    cfg = get_config()
    out = {k: v for k, v in cfg.items() if k in ["unit_amount","stop_gain_pct","overweight_band","ma_short","ma_long","ma_risk","tushare_token"]}
    if "tushare_token" in out and out["tushare_token"]:
        out["tushare_token"] = "***masked***"
    return out

@app.post("/api/settings/update")
def api_settings_update(body: SettingsUpdate):
    """更新系统配置（支持部分字段更新），写入 operation_log"""
    log = LogContext("UPDATE_CONFIG")
    try:
        updated = update_config({k:v for k,v in body.dict().items() if v is not None}, log)
        log.write("OK")
        return {"message":"ok","updated": updated}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ===== Logs（操作日志接口） =====
@app.get("/api/logs/search")
def api_logs_search(
    page: int = 1, size: int = 20,
    action: Optional[str] = None,
    query: Optional[str] = None,
    ts_from: Optional[str] = None,
    ts_to: Optional[str] = None,
):
    """查询操作日志（支持按时间区间、action、关键字检索）"""
    total, items = search_logs(query, action, ts_from, ts_to, page, size)
    return {"total": total, "items": items}

# ===== Instrument（标的管理接口） =====
class InstrumentUpdate(BaseModel):
    ts_code: str
    active: bool

    # ===== Category / Instrument Create（可选：逐条创建） =====
class CategoryCreate(BaseModel):
    name: str
    sub_name: str = ""
    target_units: float

class InstrumentCreate(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True


@app.post("/api/instrument/update")
def api_instrument_update(body: InstrumentUpdate):
    """更新某个标的的启用状态（active=0/1），写入 operation_log"""
    log = LogContext("UPDATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        with get_conn() as conn:
            conn.execute("UPDATE instrument SET active=? WHERE ts_code=?", (1 if body.active else 0, body.ts_code))
            conn.commit()
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message":"ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/api/category/create")
def api_category_create(body: CategoryCreate):
    log = LogContext("CREATE_CATEGORY")
    log.set_payload(body.dict())
    try:
        new_id = create_category(body.name, body.sub_name, body.target_units, log)
        log.write("OK")
        return {"message":"ok", "id": new_id}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instrument/create")
def api_instrument_create(body: InstrumentCreate):
    log = LogContext("CREATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        create_instrument(body.ts_code, body.name, body.category_id, body.active, log)
        log.write("OK")
        return {"message":"ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ===== Opening Position（一次性开账） =====
class OpeningPos(BaseModel):
    ts_code: str
    shares: float
    avg_cost: float
    date: str  # YYYY-MM-DD（作为 last_update 记录）

@app.post("/api/position/set_opening")
def api_set_opening_position(body: OpeningPos):
    log = LogContext("SET_OPENING_POSITION")
    log.set_payload(body.dict())
    try:
        after = set_opening_position(body.ts_code, body.shares, body.avg_cost, body.date, log)
        log.write("OK")
        return {"message":"ok", "position": after}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
# ===== Position 编辑页 API =====
from pydantic import BaseModel

class PositionUpdateBody(BaseModel):
    ts_code: str
    shares: float | None = None
    avg_cost: float | None = None
    date: str  # YYYY-MM-DD

@app.get("/api/position/raw")
def api_position_raw():
    """读取 position 表（底仓），用于‘持仓编辑’页面"""
    return list_positions_raw()

@app.post("/api/position/update")
def api_position_update(body: PositionUpdateBody):
    """更新一条底仓记录（shares/avg_cost 二选一或都传）"""
    log = LogContext("UPDATE_POSITION")
    log.set_payload(body.dict())
    try:
        out = update_position_one(body.ts_code, body.shares, body.avg_cost, body.date, log)
        log.write("OK")
        return {"message":"ok", "position": out}
    except ValueError as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
# 查询标的列表（下拉联想）
@app.get("/api/instrument/list")
def api_instrument_list(q: str | None = None, active_only: bool = True):
    """用于前端下拉选择：支持模糊搜索 ts_code/name；默认只返回 active 标的"""
    return list_instruments(q, active_only)

# 列出类别（给前端下拉）
@app.get("/api/category/list")
def api_category_list():
    return list_categories()

# 创建 instrument（如果已存在会被替换/更新）
from pydantic import BaseModel
class InstrumentCreate(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True

@app.post("/api/instrument/create")
def api_instrument_create(body: InstrumentCreate):
    log = LogContext("CREATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        create_instrument(body.ts_code, body.name, body.category_id, body.active, log)
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message":"ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))
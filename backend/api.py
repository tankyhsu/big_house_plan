# ===============================
# portfolio-ui-api  (FastAPI)
# 说明：
# - 路由按“功能域”分组并排序，便于维护与查阅
# - 所有会改动数据口径的写操作，保存后自动触发当日/交易日重算(calc)
# - 统一启用 CORS，方便本地前后端分离开发
# ===============================

from datetime import datetime
from typing import Optional, Literal, List

from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .logs import ensure_log_schema, LogContext, search_logs
from .db import get_conn
from .services.config_svc import get_config, update_config
from .services.position_svc import list_positions_raw, set_opening_position, update_position_one, delete_position
from .services.instrument_svc import create_instrument, list_instruments, seed_load, get_instrument_detail, edit_instrument
from .services.category_svc import create_category, list_categories, update_category as svc_update_category
from .services.txn_svc import create_txn, list_txn, bulk_txn
from .domain.txn_engine import round_price, round_quantity, round_shares, round_amount
from .services.pricing_svc import sync_prices_tushare
from .services.calc_svc import calc
from .services.dashboard_svc import get_dashboard, list_category, list_position, list_signal, list_signal_all, aggregate_kpi
from .services.watchlist_svc import ensure_watchlist_schema, list_watchlist, add_to_watchlist, remove_from_watchlist
from .services.analytics_svc import compute_position_xirr, compute_position_xirr_batch
from .services.utils import yyyyMMdd_to_dash
from .db import get_conn
from .repository.instrument_repo import set_active as repo_set_active
from .services.config_svc import ensure_default_config
from .providers.tushare_provider import TuShareProvider

from threading import Thread
from datetime import datetime
from .logs import LogContext, ensure_log_schema

# -----------------------------------------------------------------------------
# App 初始化 & 中间件
# -----------------------------------------------------------------------------
app = FastAPI(title="portfolio-ui-api", version="0.1.0")

# 允许前端开发端口访问（Vite 默认 5173，支持端口范围防止自动切换端口导致的跨域问题）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:5176", "http://127.0.0.1:5176",
        "http://localhost:5177", "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """启动时确保日志/表结构，并后台同步一次“今天”的价格（无 token 将跳过而不报错）"""
    ensure_log_schema()
    ensure_default_config()
    # ensure watchlist table exists
    try:
        ensure_watchlist_schema()
    except Exception as e:
        LogContext("STARTUP").write("ERROR", f"ensure_watchlist_schema_failed: {e}")

    # def _sync_once():
    #     try:
    #         today = datetime.now().strftime("%Y%m%d")
    #         log = LogContext("SYNC_ON_STARTUP")
    #         sync_prices_tushare(today, log)  # 无 token 时会返回 reason=no_token
    #         log.write("OK")
    #     except Exception as e:
    #         LogContext("SYNC_ON_STARTUP").write("ERROR", str(e))

    # Thread(target=_sync_once, daemon=True).start()

# -----------------------------------------------------------------------------
# 基础：健康检查 / 版本
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    """健康检查接口，用于确认 API 服务是否正常运行"""
    return {"status": "ok"}

@app.get("/version")
def version():
    """返回 API 服务的版本信息"""
    return {"app": "portfolio-ui-api", "version": "0.1.0"}


# =============================================================================
# 一、Dashboard / 视图（只读）
# =============================================================================
@app.get("/api/dashboard")
def api_dashboard(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    组合总览：指定 YYYYMMDD 返回总市值、成本、收益、信号统计、是否价格回退等。
    数据源为 portfolio_daily / category_daily / signal。
    """
    return get_dashboard(date)

@app.get("/api/dashboard/aggregate")
def api_dashboard_aggregate(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    period: Literal["day", "week", "month"] = Query("day")
):
    """
    聚合区间内的 Dashboard KPI 序列（day/week/month）。
    返回 items: [{date: YYYY-MM-DD, market_value, cost, unrealized_pnl, ret}]
    """
    try:
        items = aggregate_kpi(start, end, period)
        return {"period": period, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Dashboard/Series: 持仓市值历史（单个/多个）
# =============================================================================
@app.get("/api/series/position")
def api_series_position(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    ts_codes: str = Query(..., description="逗号分隔的 ts_code 列表"),
):
    try:
        if not ts_codes:
            return {"items": []}
        # 参数规范化
        codes = [c.strip() for c in ts_codes.split(',') if c and c.strip()]
        if not codes:
            return {"items": []}
        sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
        ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"
        placeholders = ",".join(["?"] * len(codes))
        sql = f"""
            SELECT pd.trade_date AS date, pd.ts_code, pd.market_value, i.name
            FROM portfolio_daily pd
            JOIN instrument i ON i.ts_code = pd.ts_code
            WHERE pd.trade_date BETWEEN ? AND ?
              AND pd.ts_code IN ({placeholders})
            ORDER BY pd.trade_date ASC
        """
        with get_conn() as conn:
            rows = conn.execute(sql, (sd, ed, *codes)).fetchall()
            items = [
                {
                    "date": r["date"],
                    "ts_code": r["ts_code"],
                    "name": r["name"],
                    "market_value": round_amount(float(r["market_value"] or 0.0)),
                }
                for r in rows
            ]
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/category")
def api_category(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    类别分布：指定 YYYYMMDD 返回各类别的市值/成本/收益/目标份/实际份/份差/配置偏离等。
    """
    return list_category(date)

@app.get("/api/position")
def api_position(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    标的持仓：指定 YYYYMMDD 返回各标的（按当天价格）计算的持仓视图及止盈信号标记。
    """
    return list_position(date)

@app.get("/api/signal")
def api_signal(date: str = Query(..., pattern=r"^\d{8}$"), type: Optional[str] = Query(None), ts_code: Optional[str] = Query(None)):
    """
    信号列表：返回当日触发的信号（止盈/配置偏离）。
    type 可选过滤。
    ts_code 可选按标的代码过滤。
    """
    return list_signal(date, type, ts_code)

@app.get("/api/signal/all")
def api_signal_all(
    type: Optional[str] = Query(None), 
    ts_code: Optional[str] = Query(None), 
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"), 
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    历史信号列表：返回历史信号，按日期倒序。
    支持日期范围筛选，默认返回所有信号。
    """
    return list_signal_all(type, ts_code, start_date, end_date, limit)

@app.get("/api/signal/zig/test")
def api_zig_signal_test(
    ts_code: str = Query(..., description="标的代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    ZIG信号测试验证接口：返回指定标的在指定时间段内的ZIG指标计算结果
    用于与通达信数据对比验证算法准确性
    """
    from backend.services.signal_svc import TdxZigSignalGenerator
    return TdxZigSignalGenerator.test_zig_calculation(ts_code, start_date, end_date)

@app.post("/api/signal/zig/validate")
def api_zig_signal_validate():
    """
    验证ZIG算法与通达信数据的一致性
    使用预设的测试数据进行验证
    """
    from backend.services.signal_svc import TdxZigSignalGenerator
    
    # 通达信测试数据 - 扩展为3个标的
    test_cases = [
        {
            "ts_code": "301606.SZ",
            "expected_buy_dates": ["2025-07-24", "2025-09-05"],
            "expected_sell_dates": ["2025-06-11", "2025-08-29"]
        },
        {
            "ts_code": "300573.SZ", 
            "expected_buy_dates": ["2025-04-08", "2025-05-29", "2025-06-23"],
            "expected_sell_dates": ["2025-05-07", "2025-06-05", "2025-09-02"]
        },
        {
            "ts_code": "002847.SZ",
            "expected_buy_dates": ["2025-08-04"], 
            "expected_sell_dates": ["2025-06-05", "2025-09-02"]
        }
    ]
    
    results = []
    overall_stats = {
        "total_cases": len(test_cases),
        "perfect_matches": 0,
        "total_expected_signals": 0,
        "total_matched_signals": 0
    }
    
    for case in test_cases:
        result = TdxZigSignalGenerator.validate_against_tdx_data(
            case["ts_code"], 
            case["expected_buy_dates"], 
            case["expected_sell_dates"]
        )
        
        results.append(result)
        
        if "accuracy" in result:
            overall_stats["total_expected_signals"] += result["accuracy"]["total_expected_signals"]
            overall_stats["total_matched_signals"] += result["accuracy"]["total_matched_signals"]
            
            if result["accuracy"]["accuracy_rate"] == 100.0:
                overall_stats["perfect_matches"] += 1
    
    # 计算总体准确率
    if overall_stats["total_expected_signals"] > 0:
        overall_accuracy = (overall_stats["total_matched_signals"] / overall_stats["total_expected_signals"]) * 100
    else:
        overall_accuracy = 0.0
    
    return {
        "validation_summary": {
            "total_test_cases": overall_stats["total_cases"],
            "perfect_accuracy_cases": overall_stats["perfect_matches"],
            "overall_accuracy_rate": round(overall_accuracy, 1),
            "total_expected_signals": overall_stats["total_expected_signals"],
            "total_matched_signals": overall_stats["total_matched_signals"]
        },
        "detailed_results": results
    }

class SignalCreate(BaseModel):
    trade_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="信号日期 YYYY-MM-DD")
    ts_code: Optional[str] = Field(None, description="标的代码（兼容性）")
    category_id: Optional[int] = Field(None, description="类别ID（兼容性）")
    scope_type: str = Field("INSTRUMENT", pattern="^(INSTRUMENT|CATEGORY|MULTI_INSTRUMENT|MULTI_CATEGORY|ALL_INSTRUMENTS|ALL_CATEGORIES)$", description="信号范围类型")
    scope_data: Optional[List[str]] = Field(None, description="范围数据数组")
    level: str = Field(..., pattern="^(HIGH|MEDIUM|LOW|INFO)$", description="信号级别")
    type: str = Field(..., description="信号类型")
    message: str = Field(..., max_length=500, description="信号描述信息")

# =============================================================================
# Watchlist / 自选关注
# =============================================================================
class WatchlistAdd(BaseModel):
    ts_code: str
    note: Optional[str] = None


@app.get("/api/watchlist")
def api_watchlist(date: Optional[str] = Query(None, pattern=r"^\d{8}$")):
    try:
        items = list_watchlist(with_last_price=True, on_date_yyyymmdd=date)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlist/add")
def api_watchlist_add(body: WatchlistAdd):
    try:
        add_to_watchlist(body.ts_code, body.note)
        return {"message": "ok"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlist/remove")
def api_watchlist_remove(ts_code: str = Body(..., embed=True)):
    try:
        remove_from_watchlist(ts_code)
        return {"message": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/signal/rebuild-historical")
def api_rebuild_historical_signals():
    """
    重建所有历史信号：清除现有自动信号，重新生成完整的历史信号
    用于信号管理和初始化
    """
    from .services.signal_svc import rebuild_all_historical_signals
    result = rebuild_all_historical_signals()
    return {"message": "历史信号重建完成", "generated_signals": result["count"], "date_range": result["date_range"]}

@app.post("/api/signal/rebuild-structure")
def api_rebuild_structure_signals():
    """
    重建结构信号：清除现有结构信号，重新生成完整的历史结构信号
    用于结构信号管理和初始化
    """
    from .services.signal_svc import SignalGenerationService
    from datetime import datetime, timedelta
    
    # 重建最近30天的结构信号
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    result = SignalGenerationService.rebuild_structure_signals_for_period(start_date, end_date)
    return {
        "message": "结构信号重建完成", 
        "generated_signals": result["total_signals"], 
        "processed_dates": result["processed_dates"],
        "date_range": result["date_range"]
    }


@app.post("/api/signal/create")
def api_signal_create(signal: SignalCreate):
    """
    手动创建信号：支持添加自定义信号（如利空/利好等政策面信号）。
    支持多种范围类型：单个标的/类别、多个标的/类别、所有标的/类别。
    """
    from .services.signal_svc import create_manual_signal_extended
    result = create_manual_signal_extended(
        trade_date=signal.trade_date,
        ts_code=signal.ts_code,  # 兼容性
        category_id=signal.category_id,  # 兼容性  
        scope_type=signal.scope_type,
        scope_data=signal.scope_data,
        level=signal.level,
        type=signal.type,
        message=signal.message
    )
    return {"message": "信号创建成功", "signal_id": result}

@app.get("/api/signals/current-status")
def api_signals_current_status(date: str = Query(..., pattern=r"^\d{8}$")):
    """
    获取当前信号状态聚合：分离历史事件信号和实时持仓状态
    返回格式：
    {
        "event_signals": [...],     # 历史事件信号（来自signal表）
        "position_status": [...],   # 实时持仓状态（基于成本计算）
        "summary": {
            "event_counts": {"stop_gain": 0, "stop_loss": 1},
            "position_counts": {"stop_gain": 2, "stop_loss": 0, "normal": 5}
        }
    }
    """
    from .services.signal_svc import SignalService
    from .services.position_status_svc import PositionStatusService
    
    # 获取历史事件信号
    event_signals = SignalService.get_signals_by_date(date)
    
    # 获取实时持仓状态  
    position_status = PositionStatusService.get_current_position_status(date)
    
    # 统计汇总
    event_counts = SignalService.get_signal_counts_by_date(yyyyMMdd_to_dash(date))
    position_counts = PositionStatusService.get_position_alerts_count(date)
    
    return {
        "date": yyyyMMdd_to_dash(date),
        "event_signals": event_signals,
        "position_status": position_status, 
        "summary": {
            "event_counts": {"stop_gain": event_counts.get("stop_gain", 0), "stop_loss": event_counts.get("stop_loss", 0)},
            "position_counts": position_counts
        }
    }

@app.get("/api/positions/status")
def api_positions_status(date: str = Query(..., pattern=r"^\d{8}$"), ts_code: Optional[str] = Query(None)):
    """
    获取持仓实时状态：基于成本的客观计算结果
    """
    from .services.position_status_svc import PositionStatusService
    
    if ts_code:
        result = PositionStatusService.get_position_status_by_instrument(ts_code, date)
        return result if result else {"error": "未找到该标的的持仓"}
    else:
        return PositionStatusService.get_current_position_status(date)


# =============================================================================
# 二、设置 / 配置（读写）
# =============================================================================
class SettingsUpdate(BaseModel):
    unit_amount: Optional[float] = None
    stop_gain_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    overweight_band: Optional[float] = None
    ma_short: Optional[int] = None
    ma_long: Optional[int] = None
    ma_risk: Optional[int] = None
    tushare_token: Optional[str] = None
    recalc_date: Optional[str] = None  # 可选：更新后重算某个 YYYYMMDD

@app.get("/api/settings/get")
def api_settings_get():
    """获取当前系统配置（unit_amount, 止盈阈值, 配置带宽等；tushare_token 会做掩码）"""
    cfg = get_config()
    fields = ["unit_amount", "stop_gain_pct", "stop_loss_pct", "overweight_band", "ma_short", "ma_long", "ma_risk", "tushare_token"]
    out = {k: v for k, v in cfg.items() if k in fields}
    if out.get("tushare_token"):
        out["tushare_token"] = "***masked***"
    return out

class SettingsUpdateBody(BaseModel):
    updates: dict

@app.post("/api/settings/update")
def api_settings_update(body: SettingsUpdateBody):
    log = LogContext("SETTINGS_UPDATE")
    log.set_payload(body.dict())
    try:
        updated_keys = update_config(body.updates, log)
        # unit_amount 变更后不需要重算，因为份数现在是实时计算的
        log.write("OK")
        return {"message": "ok", "updated": updated_keys}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# 三、参考数据：类别 / 标的（读写）
# =============================================================================
class CategoryCreate(BaseModel):
    name: str
    sub_name: str = ""
    target_units: float

class CategoryUpdate(BaseModel):
    id: int
    sub_name: Optional[str] = None
    target_units: Optional[float] = None

class CategoryUpdateItem(BaseModel):
    id: int
    sub_name: Optional[str] = None
    target_units: Optional[float] = None

class CategoryBulkUpdate(BaseModel):
    items: List[CategoryUpdateItem]

class InstrumentCreate(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True
    type: Optional[str] = None  # NEW: STOCK / FUND / CASH

class InstrumentUpdate(BaseModel):
    ts_code: str
    active: bool
    type: Optional[str] = None  # NEW: STOCK / FUND / CASH

class InstrumentEdit(BaseModel):
    ts_code: str
    name: str
    category_id: int
    active: bool = True
    type: Optional[str] = None

@app.get("/api/category/list")
def api_category_list():
    """列出所有类别（用于前端下拉选择）"""
    return list_categories()

@app.post("/api/category/create")
def api_category_create(body: CategoryCreate):
    """创建类别（name/sub_name 唯一），target_units 为目标配置份数（单位：份）"""
    log = LogContext("CREATE_CATEGORY")
    log.set_payload(body.dict())
    try:
        new_id = create_category(body.name, body.sub_name, body.target_units, log)
        log.write("OK")
        return {"message": "ok", "id": new_id}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/category/update")
def api_category_update(body: CategoryUpdate):
    """更新类别信息：仅允许修改二级分类(sub_name)与目标份数(target_units)，大类名称不可修改。"""
    log = LogContext("UPDATE_CATEGORY")
    log.set_payload(body.dict())
    try:
        if body.sub_name is None and body.target_units is None:
            raise HTTPException(status_code=400, detail="at_least_one_field_required")
        updated = svc_update_category(body.id, sub_name=body.sub_name, target_units=body.target_units, log=log)
        log.write("OK")
        return {"message": "ok", "category": updated}
    except HTTPException:
        raise
    except Exception as e:
        log.write("ERROR", str(e))
        # 可能触发唯一性约束冲突
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/category/bulk-update")
def api_category_bulk_update(body: CategoryBulkUpdate):
    """
    批量更新类别：仅支持 sub_name / target_units。若总目标份数 < 150，则自动将剩余份数分配到“现金”类别。
    现金类别由 config.cash_ts_code -> instrument(category_id) 推导。
    """
    log = LogContext("BULK_UPDATE_CATEGORY")
    log.set_payload({"items": [it.dict() for it in body.items]})
    MAX_UNITS = 150.0
    try:
        # 读取当前分类与现金类别ID
        with get_conn() as conn:
            all_rows = conn.execute("SELECT id, name, sub_name, target_units FROM category").fetchall()
            cur = {r["id"]: {"id": r["id"], "name": r["name"], "sub_name": r["sub_name"], "target_units": float(r["target_units"] or 0.0)} for r in all_rows}

            # 应用请求内的修改得到“期望的”目标份数字典
            desired = {cid: {**row} for cid, row in cur.items()}
            for it in body.items:
                if it.id not in desired:
                    raise HTTPException(status_code=400, detail=f"category_not_found: {it.id}")
                if it.sub_name is not None:
                    desired[it.id]["sub_name"] = it.sub_name
                if it.target_units is not None:
                    try:
                        desired[it.id]["target_units"] = float(it.target_units)
                    except Exception:
                        raise HTTPException(status_code=400, detail=f"invalid_target_units: {it.target_units}")

            # 计算合计并剩余
            total = sum(v.get("target_units", 0.0) for v in desired.values())
            if total > MAX_UNITS + 1e-8:
                raise HTTPException(status_code=400, detail=f"total_units_exceed_{MAX_UNITS}")
            remainder = max(0.0, MAX_UNITS - total)

            # 找到现金类别ID
            from .services.config_svc import get_config
            from .repository.instrument_repo import get_one as inst_get_one
            cfg = get_config()
            cash_code = cfg.get("cash_ts_code")
            cash_cat_id = None
            cash_cat_name = None
            cash_cat_sub = None
            if cash_code:
                inst = inst_get_one(conn, cash_code)
                if inst is not None:
                    inst_dict = dict(inst)
                    if inst_dict.get("category_id") is not None:
                        cash_cat_id = int(inst_dict["category_id"])
                        cat_row = conn.execute("SELECT name, sub_name FROM category WHERE id=?", (cash_cat_id,)).fetchone()
                        if cat_row is not None:
                            cash_cat_name = cat_row["name"]
                            cash_cat_sub = cat_row["sub_name"]

            before = {cid: cur[cid] for cid in desired.keys() if cid in cur}

            # 自动把剩余分配到现金类别
            auto_fill = 0.0
            if remainder > 1e-8 and cash_cat_id is not None and cash_cat_id in desired:
                desired[cash_cat_id]["target_units"] = float(desired[cash_cat_id].get("target_units", 0.0)) + remainder
                auto_fill = remainder

            # 写回变化的记录
            for cid, row in desired.items():
                old = cur.get(cid)
                if not old:
                    continue
                changed = False
                fields = []
                params = []
                if row["sub_name"] != old["sub_name"]:
                    fields.append("sub_name=?"); params.append(row["sub_name"]); changed = True
                if abs(float(row["target_units"]) - float(old["target_units"])) > 1e-9:
                    fields.append("target_units=?"); params.append(float(row["target_units"])); changed = True
                if changed:
                    params.append(cid)
                    sql = f"UPDATE category SET {', '.join(fields)} WHERE id=?"
                    conn.execute(sql, params)
            conn.commit()

            # 读取 after 快照
            all_rows2 = conn.execute("SELECT id, name, sub_name, target_units FROM category").fetchall()
            after = {r["id"]: {"id": r["id"], "name": r["name"], "sub_name": r["sub_name"], "target_units": float(r["target_units"] or 0.0)} for r in all_rows2}

        log.set_before(before)
        log.set_after({"auto_fill": auto_fill, "cash_category": {"id": cash_cat_id, "name": cash_cat_name, "sub_name": cash_cat_sub} if cash_cat_id is not None else None, "after": after})
        log.write("OK")
        return {
            "message": "ok",
            "auto_fill": auto_fill,
            "total": sum(v.get("target_units", 0.0) for v in after.values()),
            "cash_category": ({"id": cash_cat_id, "name": cash_cat_name, "sub_name": cash_cat_sub} if cash_cat_id is not None else None)
        }
    except HTTPException:
        log.write("ERROR", "bad_request")
        raise
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/instrument/list")
def api_instrument_list(q: Optional[str] = None, active_only: bool = True):
    """
    标的列表（下拉联想）：支持按 ts_code/name 模糊搜，默认只返回 active=1。
    前端 AutoComplete 用于“新增交易”等场景。
    """
    return list_instruments(q, active_only)

@app.get("/api/instrument/get")
def api_instrument_get(ts_code: str = Query(...)):
    """获取单个标的详情（含类别名称）。"""
    try:
        row = get_instrument_detail(ts_code)
        if not row:
            raise HTTPException(status_code=404, detail="instrument_not_found")
        # 统一布尔类型
        row["active"] = bool(row.get("active"))
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instrument/create")
def api_instrument_create(body: InstrumentCreate, recalc_today: bool = Query(False)):
    """
    创建/更新标的映射；可选 recalc_today=True 时，保存后重算“今天”的快照。
    通常不需要重算，仅结构性数据准备。
    """
    log = LogContext("CREATE_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        create_instrument(body.ts_code, body.name, body.category_id, body.active, log, sec_type=body.type)
        if recalc_today:
            today = datetime.now().strftime("%Y%m%d")
            calc(today, LogContext("CALC_AFTER_INSTRUMENT_CREATE"))
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instrument/update")
def api_instrument_update(body: InstrumentUpdate):
    """更新标的启用状态（active=0/1）"""
    log = LogContext("UPDATE_INSTRUMENT")
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

@app.post("/api/instrument/edit")
def api_instrument_edit(body: InstrumentEdit):
    """编辑标的基础信息（名称/类别/启用/类型）。"""
    log = LogContext("EDIT_INSTRUMENT")
    log.set_payload(body.dict())
    try:
        edit_instrument(body.ts_code, body.name, int(body.category_id), bool(body.active), body.type, log)
        log.set_entity("INSTRUMENT", body.ts_code)
        log.write("OK")
        return {"message": "ok"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/seed/load")
def api_seed_load_route(
    categories_csv: str = Body(...),
    instruments_csv: str = Body(...),
    recalc_today: bool = Query(False)
):
    """
    从 CSV 导入类别与标的：
      - categories.csv: name, sub_name, target_units
      - instruments.csv: ts_code, name, category_name, category_sub_name, active
    可选 recalc_today=True 时，导入后重算“今天”。
    """
    log = LogContext("SEED_LOAD")
    log.set_payload({"categories_csv": categories_csv, "instruments_csv": instruments_csv})
    try:
        res = seed_load(categories_csv, instruments_csv, log)
        if recalc_today:
            today = datetime.now().strftime("%Y%m%d")
            calc(today, LogContext("CALC_AFTER_SEED_LOAD"))
        log.write("OK")
        return {"message": "ok", **res}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 四、交易（读写）——保存后按交易日自动重算
# =============================================================================
class TxnCreate(BaseModel):
    ts_code: str
    date: str  # YYYY-MM-DD
    action: Literal["BUY", "SELL", "DIV", "FEE", "ADJ"]
    shares: float
    price: Optional[float] = None
    amount: Optional[float] = None
    fee: Optional[float] = None
    notes: Optional[str] = None

@app.get("/api/txn/list")
def api_txn_list(page: int = 1, size: int = 20):
    """分页查询历史交易流水"""
    total, items = list_txn(page, size)
    return {"total": total, "items": items}

@app.get("/api/txn/range")
def api_txn_range(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    ts_codes: Optional[str] = Query(None, description="逗号分隔，可选：限定标的"),
):
    """
    区间内交易流水（可按标的过滤）。
    返回 items: [{date: YYYY-MM-DD, ts_code, name, action, shares, price, amount, fee}]
    """
    try:
        sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
        ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"
        codes: list[str] = []
        if ts_codes:
            codes = [c.strip() for c in ts_codes.split(',') if c and c.strip()]

        base_sql = (
            "SELECT t.trade_date AS date, t.ts_code, i.name AS name, t.action, t.shares, t.price, t.amount, t.fee "
            "FROM txn t LEFT JOIN instrument i ON i.ts_code = t.ts_code "
            "WHERE t.trade_date >= ? AND t.trade_date <= ?"
        )
        params: list[object] = [sd, ed]
        if codes:
            placeholders = ",".join(["?"] * len(codes))
            base_sql += f" AND t.ts_code IN ({placeholders})"
            params.extend(codes)
        base_sql += " ORDER BY t.trade_date ASC, t.id ASC"

        with get_conn() as conn:
            rows = conn.execute(base_sql, params).fetchall()
            items = [
                {
                    "date": r["date"],
                    "ts_code": r["ts_code"],
                    "name": r["name"],
                    "action": r["action"],
                    "shares": round_shares(float(r["shares"] or 0.0)),
                    "price": (round_price(float(r["price"])) if r["price"] is not None else None),
                    "amount": (round_amount(float(r["amount"])) if r["amount"] is not None else None),
                    "fee": (round_amount(float(r["fee"])) if r["fee"] is not None else None),
                }
                for r in rows
            ]
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/txn/create", status_code=201)
def api_txn_create(body: TxnCreate):
    """
    新增一笔交易（BUY/SELL/DIV/FEE/ADJ），并更新 position（均价法）。
    保存后会按交易日 YYYYMMDD 重算快照。
    """
    log = LogContext("CREATE_TXN")
    log.set_payload(body.dict())
    try:
        res = create_txn(body.dict(), log)
        date_yyyymmdd = body.date.replace("-", "")
        calc(date_yyyymmdd, LogContext("CALC_AFTER_TXN_CREATE"))
        log.write("OK")
        return {"message": "ok", "position": res}
    except ValueError as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail="internal error")

class BulkTxnReq(BaseModel):
    items: List[TxnCreate]
    recalc: Literal["none", "latest", "all"] = "latest"  # 重算策略

@app.post("/api/txn/bulk")
def api_txn_bulk(body: BulkTxnReq):
    """
    批量导入交易：
      - recalc="latest"（默认）：只重算导入中最新日期
      - recalc="all"：重算涉及到的全部日期（>50 天将退化为只算最新，避免长阻塞）
      - recalc="none"：不重算（不推荐）
    """
    log = LogContext("BULK_TXN")
    log.set_payload({"count": len(body.items), "recalc": body.recalc})
    try:
        ok, fail, errs = 0, 0, []
        date_set = set()
        for i, t in enumerate(body.items):
            try:
                create_txn(t.dict(), log)
                ok += 1
                date_set.add(t.date.replace("-", ""))
            except Exception as e:
                fail += 1
                errs.append({"index": i, "ts_code": t.ts_code, "error": str(e)})

        if body.recalc != "none" and date_set:
            if body.recalc == "latest":
                calc(max(date_set), LogContext("CALC_AFTER_TXN_BULK_LATEST"))
            else:  # "all"
                dates = sorted(date_set)
                if len(dates) > 50:
                    calc(dates[-1], LogContext("CALC_AFTER_TXN_BULK_GUARDED"))
                else:
                    for d in dates:
                        calc(d, LogContext("CALC_AFTER_TXN_BULK_ALL"))

        log.set_after({"ok": ok, "fail": fail})
        log.write("OK")
        return {"message": "ok", "ok": ok, "fail": fail, "errors": errs}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 五、持仓（读写）——底仓编辑/开账，保存后自动重算
# =============================================================================
class OpeningPos(BaseModel):
    ts_code: str
    shares: float
    avg_cost: float
    date: str  # YYYY-MM-DD（作为 last_update 记录）

class PositionUpdateBody(BaseModel):
    ts_code: str
    shares: Optional[float] = None
    avg_cost: Optional[float] = None
    date: str  # YYYY-MM-DD
    opening_date: Optional[str] = None  # YYYY-MM-DD，可选

@app.get("/api/position/raw")
def api_position_raw(include_zero: bool = Query(True, description="是否包含 shares<=0 的持仓")):
    return list_positions_raw(include_zero=include_zero)

@app.post("/api/position/set_opening")
def api_set_opening_position(body: OpeningPos):
    """
    一次性设置初始持仓（开账）。适合已有底仓不想录入历史流水的场景。
    保存后按该日期 YYYYMMDD 自动重算。
    """
    log = LogContext("SET_OPENING_POSITION")
    log.set_payload(body.dict())
    try:
        after = set_opening_position(body.ts_code, body.shares, body.avg_cost, body.date, log)
        date_yyyymmdd = body.date.replace("-", "")
        calc(date_yyyymmdd, LogContext("CALC_AFTER_OPENING"))
        log.write("OK")
        return {"message": "ok", "position": after}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/position/update")
def api_position_update(body: PositionUpdateBody):
    """
    更新一条底仓记录（shares/avg_cost 任一或两者）。
    注意：用于初始化/纠错；日常变动建议用交易流水维护。
    保存后按该日期 YYYYMMDD 自动重算。
    """
    log = LogContext("UPDATE_POSITION")
    log.set_payload(body.dict())
    try:
        out = update_position_one(body.ts_code, body.shares, body.avg_cost, body.date, log, opening_date=body.opening_date)
        date_yyyymmdd = body.date.replace("-", "")
        calc(date_yyyymmdd, LogContext("CALC_AFTER_POSITION_UPDATE"))
        log.write("OK")
        return {"message": "ok", "position": out}
    except ValueError as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

class DeletePosBody(BaseModel):
    ts_code: str
    recalc_date: Optional[str] = None  # YYYYMMDD，可选

@app.post("/api/position/delete")
def api_position_delete(body: DeletePosBody):
    log = LogContext("DELETE_POSITION")
    log.set_payload(body.dict())
    try:
        n = delete_position(body.ts_code)
        if body.recalc_date:
            calc(body.recalc_date, LogContext("CALC_AFTER_POSITION_DELETE"))
        log.write("OK")
        return {"message": "ok", "deleted": n}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))



# =============================================================================
# 六、计算 / 同步价格 / 报表（触发类）
# =============================================================================
class DateBody(BaseModel):
    date: Optional[str] = None  # YYYYMMDD；不传则用今天

@app.post("/api/calc")
def api_calc(body: DateBody = Body(default=DateBody())):
    """对指定日期进行快照计算，更新 portfolio_daily / category_daily / signal"""
    date = body.date or datetime.now().strftime("%Y%m%d")
    log = LogContext("CALC_SNAPSHOT")
    try:
        calc(date, log)
        log.write("OK")
        return {"message": "ok", "date": f"{date[0:4]}-{date[4:6]}-{date[6:8]}"}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/signal/generate-structure")  
def api_generate_structure_signals(body: DateBody = Body(default=DateBody())):
    """
    为指定日期生成结构信号（九转买入/九转卖出）
    用于日常结构信号生成
    """
    from .services.signal_svc import TdxStructureSignalGenerator
    from datetime import datetime
    
    date = body.date or datetime.now().strftime("%Y%m%d")
    # 转换为YYYY-MM-DD格式
    formatted_date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    
    signal_count, signal_instruments = TdxStructureSignalGenerator.generate_structure_signals_for_date(formatted_date)
    
    return {
        "message": "结构信号生成完成",
        "date": formatted_date, 
        "generated_signals": signal_count,
        "signal_instruments": signal_instruments
    }

@app.post("/api/signal/generate-zig")  
def api_generate_zig_signals(body: DateBody = Body(default=DateBody())):
    """
    为指定日期生成ZIG信号（ZIG买入/卖出信号）
    用于日常ZIG信号生成
    """
    from .services.signal_svc import TdxZigSignalGenerator
    from datetime import datetime
    
    date = body.date or datetime.now().strftime("%Y%m%d")
    # 转换为YYYY-MM-DD格式
    formatted_date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    
    signal_count, signal_instruments = TdxZigSignalGenerator.generate_zig_signals_for_date(formatted_date)
    
    return {
        "message": "ZIG信号生成完成",
        "date": formatted_date,
        "signal_count": signal_count,
        "signal_instruments": signal_instruments
    }

@app.post("/api/signal/zig/cleanup")  
def api_cleanup_zig_signals(body: DateBody = Body(default=DateBody())):
    """
    清理并重新生成ZIG信号 - 用于价格更新后的信号维护
    
    当价格数据更新时，ZIG指标会重新计算，可能导致之前的信号不再有效。
    此接口会：
    1. 重新计算所有标的的ZIG信号
    2. 删除不再有效的历史ZIG信号
    3. 生成新的有效信号
    4. 返回详细的清理和生成统计
    """
    from .services.signal_svc import TdxZigSignalGenerator
    from datetime import datetime
    
    date = body.date or datetime.now().strftime("%Y%m%d")
    # 转换为YYYY-MM-DD格式
    formatted_date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    
    cleanup_result = TdxZigSignalGenerator.cleanup_and_regenerate_zig_signals(formatted_date)
    
    return {
        "message": "ZIG信号清理重新生成完成",
        "date": formatted_date,
        "processed_instruments": cleanup_result["processed_instruments"],
        "deleted_signals": cleanup_result["deleted_signals"], 
        "generated_signals": cleanup_result["generated_signals"],
        "signal_changes": cleanup_result["signal_changes"]
    }

class ZigRebuildRangeBody(BaseModel):
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    ts_codes: Optional[List[str]] = Field(None, description="可选，仅重建这些标的")

@app.post("/api/signal/rebuild-zig-range")
def api_rebuild_zig_range(body: ZigRebuildRangeBody):
    """
    重建区间 ZIG 信号：
    1) 删除 [start_date, end_date] 内所有（或指定标的的）ZIG_BUY/ZIG_SELL
    2) 按交易日逐日重建，并保证 Zig 买卖交替逻辑（同类连发保留新信号）
    """
    from .services.signal_svc import TdxZigSignalGenerator
    try:
        res = TdxZigSignalGenerator.rebuild_zig_signals_for_period(
            body.start_date, body.end_date, body.ts_codes
        )
        return {"message": "ZIG区间重建完成", **res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SyncBody(BaseModel):
    date: Optional[str] = None      # YYYYMMDD；不传则今天
    recalc: bool = False            # NEW: 同步后是否自动重算
    ts_codes: Optional[List[str]] = None  # NEW: 指定要同步的标的代码列表
    days: Optional[int] = None      # NEW: 同步过去N天的数据（从指定日期往前）

@app.post("/api/sync-prices")
def api_sync_prices(body: SyncBody = Body(default=SyncBody())):
    """
    同步指定日期的收盘价/净值（TuShare），仅落库到 price_eod。
    支持：
    - 单日同步: 仅传 date 
    - 多日同步: 传 date + days，从date往前同步days天
    - 指定标的: 传 ts_codes 列表
    recalc=true 时，会按实际 used_dates_uniq 逐日自动重算（calc）。
    """
    from datetime import datetime, timedelta
    
    end_date = body.date or datetime.now().strftime("%Y%m%d")
    ts_codes = body.ts_codes
    
    # 计算要同步的日期列表
    dates_to_sync = [end_date]
    if body.days and body.days > 1:
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        dates_to_sync = []
        for i in range(body.days):
            sync_date = end_dt - timedelta(days=i)
            dates_to_sync.append(sync_date.strftime("%Y%m%d"))
    
    log = LogContext("SYNC_PRICES_TUSHARE")
    log.set_payload({"dates": dates_to_sync, "ts_codes": ts_codes, "recalc": body.recalc})
    
    all_results = []
    all_used_dates = set()
    
    try:
        # 逐日同步
        for date in dates_to_sync:
            if ts_codes:
                # 指定标的同步
                res = sync_prices_tushare(date, LogContext(f"SYNC_{date}"), ts_codes)
            else:
                # 全量同步
                res = sync_prices_tushare(date, LogContext(f"SYNC_{date}"))
            
            all_results.append(res)
            used_dates = res.get("used_dates_uniq") or [date]
            all_used_dates.update(used_dates)
        
        log.write("OK")

        if body.recalc:
            # 对所有影响的日期逐日重算
            for d in sorted(all_used_dates):
                calc(d, LogContext("CALC_AFTER_SYNC"))
        
        # 汇总结果
        total_found = sum(r.get("found", 0) for r in all_results)
        total_updated = sum(r.get("updated", 0) for r in all_results)
        total_skipped = sum(r.get("skipped", 0) for r in all_results)
        # 若所有结果均包含相同的跳过原因（如 no_token），在顶层透出该 reason 以便调用方快速判断
        summary_reason = None
        if all_results and all(r.get("reason") for r in all_results):
            reasons = {r.get("reason") for r in all_results}
            if len(reasons) == 1:
                summary_reason = reasons.pop()
        
        response = {
            "message": "ok", 
            "dates_processed": len(dates_to_sync),
            "total_found": total_found,
            "total_updated": total_updated,
            "total_skipped": total_skipped,
            "used_dates_uniq": sorted(list(all_used_dates)),
            "details": all_results
        }
        if summary_reason:
            response["reason"] = summary_reason
        return response
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=f"sync failed: {str(e)}")

@app.post("/api/report/export")
def api_export(body: DateBody = Body(default=DateBody())):
    """
    导出指定日期的报表（占位实现，返回预期文件路径列表）。
    建议后续落地 CSV/Excel/PDF 导出器。
    """
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


# =============================================================================
# 七、操作日志（只读）
# =============================================================================
@app.get("/api/logs/search")
def api_logs_search(
    page: int = 1, size: int = 20,
    action: Optional[str] = None,
    query: Optional[str] = None,
    ts_from: Optional[str] = None,
    ts_to: Optional[str] = None,
):
    """
    查询操作日志（操作时间/动作/关键字等过滤）。
    用于审计每一次写操作与自动重算行为。
    """
    total, items = search_logs(query, action, ts_from, ts_to, page, size)
    return {"total": total, "items": items}

# =============================================================================
# 八、分析 / 指标（只读）
# =============================================================================
@app.get("/api/position/irr")
def api_position_irr(ts_code: str = Query(...), date: str = Query(..., pattern=r"^\d{8}$")):
    """单标的 XIRR（资金加权年化收益，自建仓至指定日期）"""
    try:
        return compute_position_xirr(ts_code, date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/position/irr/batch")
def api_position_irr_batch(date: str = Query(..., pattern=r"^\d{8}$")):
    """批量 XIRR：对有持仓或有交易记录的标的计算"""
    try:
        return compute_position_xirr_batch(date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 九、价格（只读）
# =============================================================================
@app.get("/api/price/last")
def api_price_last(ts_code: str = Query(...), date: Optional[str] = Query(None, pattern=r"^\d{8}$")):
    """
    返回指定标的在给定日期(YYYYMMDD)之前(含)的最近收盘价与对应日期。
    若未传 date，则使用今天。
    输出: { trade_date: YYYY-MM-DD | null, close: float | null }
    """
    from datetime import datetime
    try:
        d = date or datetime.now().strftime("%Y%m%d")
        dash = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        from .repository.price_repo import get_last_close_on_or_before
        with get_conn() as conn:
            last = get_last_close_on_or_before(conn, ts_code, dash)
        if not last:
            return {"trade_date": None, "close": None}
        return {"trade_date": last[0], "close": float(last[1])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price/ohlc")
def api_price_ohlc(
    ts_code: str = Query(...),
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
):
    """
    返回指定标的在给定区间内的日线 OHLCV 数据（含可能的缺项回填为 close）。
    输出: { items: [{ date: YYYY-MM-DD, open, high, low, close, vol }] }
    """
    try:
        sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
        ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"
        sql = (
            "SELECT trade_date, open, high, low, close, vol "
            "FROM price_eod WHERE ts_code=? AND trade_date >= ? AND trade_date <= ? "
            "ORDER BY trade_date ASC"
        )
        with get_conn() as conn:
            rows = conn.execute(sql, (ts_code, sd, ed)).fetchall()
        items = []
        for r in rows:
            c = round_price(float(r["close"])) if r["close"] is not None else None
            # 若 open/high/low 缺失，退化为 close（平盘蜡烛）
            o = round_price(float(r["open"])) if r["open"] is not None else (c if c is not None else None)
            h = round_price(float(r["high"])) if r["high"] is not None else (c if c is not None else None)
            l = round_price(float(r["low"])) if r["low"] is not None else (c if c is not None else None)
            if c is None:
                # 若 close 也缺失，跳过该行
                continue
            v = round_quantity(float(r["vol"])) if ("vol" in r.keys() and r["vol"] is not None) else None
            items.append({
                "date": r["trade_date"],
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "vol": v,
            })
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 十、标的查找（TuShare 辅助）
# =============================================================================
@app.get("/api/instrument/lookup")
def api_instrument_lookup(ts_code: str = Query(...), date: Optional[str] = Query(None, pattern=r"^\d{8}$")):
    cfg = get_config()
    token = cfg.get("tushare_token")
    if not token:
        raise HTTPException(status_code=400, detail="no_tushare_token")
    prov = TuShareProvider(token)
    basic = prov.fund_basic_one(ts_code) or prov.stock_basic_one(ts_code)
    out_type = None
    name = None
    if basic:
        name = basic.get("name")
        ft = (basic.get("fund_type") or "").upper()
        if ft:
            out_type = "ETF" if "ETF" in ft else "FUND"
        else:
            out_type = "STOCK"
    if not out_type:
        if ts_code.endswith(".OF"):
            out_type = "FUND"
        elif ts_code.endswith(".SH") or ts_code.endswith(".SZ"):
            out_type = "ETF"
        else:
            out_type = "STOCK"

    price = None
    if date:
        try:
            if out_type == "STOCK":
                df = prov.daily_for_date(date)
                used = date
                if df is None or df.empty:
                    back = prov.trade_cal_backfill_recent_open(date, 30)
                    if back:
                        used = back
                        df = prov.daily_for_date(used)
                if df is not None and not df.empty:
                    import pandas as pd
                    row = df[df["ts_code"] == ts_code]
                    if not row.empty:
                        c = row.iloc[0].get("close")
                        if c is not None:
                            price = {"trade_date": f"{used[0:4]}-{used[4:6]}-{used[6:8]}", "close": float(c)}
            elif out_type == "ETF":
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(date, "%Y%m%d"); start_dt = end_dt - timedelta(days=30)
                df = prov.fund_daily_window(ts_code, start_dt.strftime("%Y%m%d"), date)
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date"); df = df[df["trade_date"] <= date]
                    if not df.empty:
                        last = df.iloc[-1]; c = last.get("close")
                        if c is not None:
                            used = str(last["trade_date"])
                            price = {"trade_date": f"{used[0:4]}-{used[4:6]}-{used[6:8]}", "close": float(c)}
            else:
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(date, "%Y%m%d"); start_dt = end_dt - timedelta(days=30)
                df = prov.fund_nav_window(ts_code, start_dt.strftime("%Y%m%d"), date)
                if df is not None and not df.empty:
                    df = df.sort_values("nav_date"); df = df[df["nav_date"] <= date]
                    if not df.empty:
                        last = df.iloc[-1]
                        nav = last.get("unit_nav") or last.get("acc_nav")
                        if nav is not None:
                            used = str(last["nav_date"])
                            price = {"trade_date": f"{used[0:4]}-{used[4:6]}-{used[6:8]}", "close": float(nav)}
        except Exception as e:
            print(f"[lookup] fetch price failed ts={ts_code} date={date}: {e}")

    return {"ts_code": ts_code, "name": name, "type": out_type, "basic": basic, "price": price}

# ===== 数据备份/恢复 =====

@app.post("/api/backup")
def api_backup():
    """备份所有业务相关数据表"""
    try:
        import json
        from datetime import datetime
        
        # 业务相关的表，排除日志表
        business_tables = [
            "config", "category", "instrument", "txn", "price_eod", 
            "ma_cache", "position", "portfolio_daily", "category_daily", "signal"
        ]
        
        backup_data = {}
        backup_data["timestamp"] = datetime.now().isoformat()
        backup_data["backup_date"] = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        backup_data["version"] = "1.0"
        backup_data["tables"] = {}
        backup_data["summary"] = {}
        
        with get_conn() as conn:
            conn.row_factory = lambda cursor, row: dict(zip([col[0] for col in cursor.description], row))
            for table in business_tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                backup_data["tables"][table] = rows
                backup_data["summary"][table] = len(rows)
        
        # 生成文件名 - 包含更详细的时间信息
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M")
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"portfolio_backup_{date_str}_{time_str}_{timestamp}.json"
        
        return Response(
            content=json.dumps(backup_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@app.post("/api/restore")
async def api_restore(file: UploadFile = File(...)):
    """从备份文件恢复数据"""
    try:
        import json
        
        # 检查文件类型
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="只支持JSON备份文件")
        
        # 读取文件内容
        content = await file.read()
        backup_data = json.loads(content.decode('utf-8'))
        
        if "tables" not in backup_data:
            raise HTTPException(status_code=400, detail="备份文件格式不正确")
        
        with get_conn() as conn:
            # 开始事务
            conn.execute("BEGIN TRANSACTION")
            
            try:
                # 清空现有业务数据（保留operation_log）
                business_tables = [
                    "signal", "category_daily", "portfolio_daily", "position", 
                    "ma_cache", "price_eod", "txn", "instrument", "category", "config"
                ]
                
                for table in business_tables:
                    if table in backup_data["tables"]:
                        conn.execute(f"DELETE FROM {table}")
                
                # 恢复数据
                for table_name, rows in backup_data["tables"].items():
                    if not rows:
                        continue
                    
                    # 获取列名
                    columns = list(rows[0].keys())
                    placeholders = ",".join(["?" for _ in columns])
                    
                    insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                    
                    for row in rows:
                        values = [row[col] for col in columns]
                        conn.execute(insert_sql, values)
                
                # 提交事务
                conn.commit()
                
                return {"message": f"数据恢复成功，共恢复 {len(backup_data['tables'])} 个表，建议手动重新计算组合数据"}
                
            except Exception as e:
                conn.rollback()
                raise e
                
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="备份文件格式错误，无法解析JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

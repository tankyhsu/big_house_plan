from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from ..services.utils import yyyyMMdd_to_dash

router = APIRouter()


class SignalCreate(BaseModel):
    trade_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    ts_code: str | None = None
    category_id: int | None = None
    scope_type: str = Field(
        "INSTRUMENT",
        pattern=r"^(INSTRUMENT|CATEGORY|MULTI_INSTRUMENT|MULTI_CATEGORY|ALL_INSTRUMENTS|ALL_CATEGORIES)$",
    )
    scope_data: list[str | None] = None
    level: str = Field(..., pattern=r"^(HIGH|MEDIUM|LOW|INFO)$")
    type: str = Field(...)
    message: str = Field(..., max_length=500)


@router.get("/api/signals/current-status")
def api_signals_current_status(date: str = Query(..., pattern=r"^\d{8}$")):
    from ..services.signal_svc import SignalService
    from ..services.position_status_svc import PositionStatusService

    event_signals = SignalService.get_signals_by_date(date)
    position_status = PositionStatusService.get_current_position_status(date)
    event_counts = SignalService.get_signal_counts_by_date(yyyyMMdd_to_dash(date))
    position_counts = PositionStatusService.get_position_alerts_count(date)

    return {
        "date": yyyyMMdd_to_dash(date),
        "event_signals": event_signals,
        "position_status": position_status,
        "summary": {
            "event_counts": {
                "stop_gain": event_counts.get("stop_gain", 0),
                "stop_loss": event_counts.get("stop_loss", 0),
            },
            "position_counts": position_counts,
        },
    }


@router.get("/api/positions/status")
def api_positions_status(date: str = Query(..., pattern=r"^\d{8}$"), ts_code: str | None = Query(None)):
    from ..services.position_status_svc import PositionStatusService

    if ts_code:
        result = PositionStatusService.get_position_status_by_instrument(ts_code, date)
        return result if result else {"error": "未找到该标的的持仓"}
    else:
        return PositionStatusService.get_current_position_status(date)


@router.get("/api/signal/zig/test")
def api_zig_signal_test(
    ts_code: str = Query(..., description="标的代码"),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
):
    from ..services.signal_svc import TdxZigSignalGenerator

    return TdxZigSignalGenerator.test_zig_calculation(ts_code, start_date, end_date)


@router.post("/api/signal/zig/validate")
def api_zig_signal_validate():
    from ..services.signal_svc import TdxZigSignalGenerator

    test_cases = [
        {
            "ts_code": "301606.SZ",
            "expected_buy_dates": ["2025-07-24", "2025-09-05"],
            "expected_sell_dates": ["2025-06-11", "2025-08-29"],
        },
        {
            "ts_code": "300573.SZ",
            "expected_buy_dates": ["2025-04-08", "2025-05-29", "2025-06-23"],
            "expected_sell_dates": ["2025-05-07", "2025-06-05", "2025-09-02"],
        },
        {
            "ts_code": "002847.SZ",
            "expected_buy_dates": ["2025-08-04"],
            "expected_sell_dates": ["2025-06-05", "2025-09-02"],
        },
        {
            "ts_code": "159915.SZ",
            "expected_buy_dates": [],
            "expected_sell_dates": [],
        },
    ]

    results = []
    overall_stats = {
        "total_cases": len(test_cases),
        "perfect_matches": 0,
        "total_expected_signals": 0,
        "total_matched_signals": 0,
    }

    for case in test_cases:
        result = TdxZigSignalGenerator.validate_against_tdx_data(
            case["ts_code"], case["expected_buy_dates"], case["expected_sell_dates"]
        )
        results.append(result)
        if "accuracy" in result:
            overall_stats["total_expected_signals"] += result["accuracy"]["total_expected_signals"]
            overall_stats["total_matched_signals"] += result["accuracy"]["total_matched_signals"]
            if result["accuracy"]["accuracy_rate"] == 100.0:
                overall_stats["perfect_matches"] += 1

    overall_accuracy = (
        (overall_stats["total_matched_signals"] / overall_stats["total_expected_signals"]) * 100
        if overall_stats["total_expected_signals"] > 0
        else 0.0
    )

    return {
        "validation_summary": {
            "total_test_cases": overall_stats["total_cases"],
            "perfect_accuracy_cases": overall_stats["perfect_matches"],
            "overall_accuracy_rate": round(overall_accuracy, 1),
            "total_expected_signals": overall_stats["total_expected_signals"],
            "total_matched_signals": overall_stats["total_matched_signals"],
        },
        "detailed_results": results,
    }


@router.post("/api/signal/rebuild-historical")
def api_rebuild_historical_signals():
    from ..services.signal_svc import rebuild_all_historical_signals

    result = rebuild_all_historical_signals()
    return {
        "message": "历史信号重建完成",
        "generated_signals": result["count"],
        "date_range": result["date_range"],
    }


@router.post("/api/signal/rebuild-structure")
def api_rebuild_structure_signals():
    from ..services.signal_svc import SignalGenerationService
    from datetime import datetime, timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    result = SignalGenerationService.rebuild_structure_signals_for_period(start_date, end_date)
    return {
        "message": "结构信号重建完成",
        "generated_signals": result["total_signals"],
        "processed_dates": result["processed_dates"],
        "date_range": result["date_range"],
    }


@router.post("/api/signal/create")
def api_signal_create(signal: SignalCreate):
    from ..services.signal_svc import create_manual_signal_extended

    result = create_manual_signal_extended(
        trade_date=signal.trade_date,
        ts_code=signal.ts_code,
        category_id=signal.category_id,
        scope_type=signal.scope_type,
        scope_data=signal.scope_data,
        level=signal.level,
        type=signal.type,
        message=signal.message,
    )
    return {"message": "信号创建成功", "signal_id": result}

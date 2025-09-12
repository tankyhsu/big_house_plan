from __future__ import annotations

from ..logs import LogContext
from .config_svc import get_config
from ..providers.tushare_provider import TuShareProvider
from .pricing_orchestrator import sync_prices as orchestrate

def sync_prices_tushare(
    trade_date: str,
    log: LogContext,
    ts_codes: list[str | None] = None,
    fund_rate_per_min: int | None = None,
) -> dict:
    """
    通过 TuShare API 同步指定交易日的价格数据
    
    Args:
        trade_date: 交易日期，格式 YYYYMMDD
        log: 日志上下文，记录同步过程
        ts_codes: 可选，指定要同步的标的代码列表。为空时同步所有活跃标的
        fund_rate_per_min: 可选，基金数据每分钟请求频率限制
        
    Returns:
        dict: 同步结果统计
        - date: 同步日期
        - found: 找到的价格数据条数  
        - updated: 更新的价格数据条数
        - skipped: 跳过的数据条数
        - reason: 跳过原因（如 no_token）
        
    说明：
        - 如果未配置 TuShare Token，将返回 reason='no_token' 并跳过同步
        - 使用速率限制避免 API 调用过于频繁
        - 实际同步逻辑委托给 pricing_orchestrator 模块
    """
    cfg = get_config()
    token = cfg.get("tushare_token")
    
    if not token:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_token"}
        log.set_after(info); log.write("DEBUG", "[sync_prices] no_token")
        return info
    
    # 从配置读取默认速率限制
    if fund_rate_per_min is None:
        try:
            v = int(cfg.get("tushare_fund_rate_per_min", 0) or 0)
            fund_rate_per_min = v if v > 0 else None
        except Exception:
            fund_rate_per_min = None
    
    provider = TuShareProvider(token, fund_rate_per_min=fund_rate_per_min)
    return orchestrate(trade_date, provider, log, ts_codes)

def find_missing_price_dates(
    lookback_days: int = 7,
    ts_codes: list[str] = None
) -> dict[str, list[str]]:
    """
    查找过去N天中缺失价格数据的日期
    
    Args:
        lookback_days: 向前查找的天数，默认7天
        ts_codes: 可选，指定要检查的标的代码列表。为空时检查所有活跃标的
        
    Returns:
        dict: {date_yyyymmdd: [missing_ts_codes]}
    """
    from ..db import get_conn
    from ..repository import price_repo
    
    with get_conn() as conn:
        return price_repo.find_missing_price_dates(conn, lookback_days, ts_codes)


def sync_prices_enhanced(
    lookback_days: int = 7, 
    ts_codes: list[str] = None,
    recalc: bool = True
) -> dict:
    """
    增强的价格同步功能：自动检测并补齐过去N天缺失的价格数据
    
    Args:
        lookback_days: 向前检查的天数，默认7天
        ts_codes: 可选，指定要同步的标的代码列表
        recalc: 是否在同步完成后自动重算
        
    Returns:
        dict: 同步结果统计
    """
    from datetime import datetime
    from ..logs import LogContext
    from .calc_svc import calc
    
    log = LogContext("SYNC_PRICES_ENHANCED")
    log.set_payload({
        "lookback_days": lookback_days, 
        "ts_codes_count": len(ts_codes) if ts_codes else None,
        "recalc": recalc
    })
    
    try:
        # 1. 查找缺失的价格数据
        missing_by_date = find_missing_price_dates(lookback_days, ts_codes)
        
        if not missing_by_date:
            result = {
                "message": "所有日期的价格数据都已完整",
                "dates_processed": 0,
                "total_found": 0,
                "total_updated": 0,
                "total_skipped": 0,
                "missing_summary": {}
            }
            log.set_after(result)
            log.write("OK", "no_missing_data")
            return result
        
        # 2. 按日期同步缺失的价格数据
        all_results = []
        all_used_dates = set()
        
        for date_yyyymmdd in sorted(missing_by_date.keys(), reverse=True):  # 从最近的日期开始
            missing_codes = missing_by_date[date_yyyymmdd]
            date_log = LogContext(f"SYNC_ENHANCED_{date_yyyymmdd}")
            
            # 只同步缺失的标的
            sync_result = sync_prices_tushare(date_yyyymmdd, date_log, missing_codes)
            all_results.append({
                "date": date_yyyymmdd,
                "missing_codes_count": len(missing_codes),
                **sync_result
            })
            
            # 收集实际使用的日期
            used_dates = sync_result.get("used_dates_uniq") or [date_yyyymmdd]
            all_used_dates.update(used_dates)
        
        # 3. 如果需要重算，对所有涉及的日期进行重算
        if recalc:
            recalc_dates = sorted(all_used_dates)
            for date_dash in recalc_dates:
                try:
                    # 转换为YYYYMMDD格式进行重算
                    date_yyyymmdd = date_dash.replace("-", "")
                    calc(date_yyyymmdd, LogContext(f"RECALC_{date_yyyymmdd}"))
                except Exception as e:
                    log.write("WARN", f"recalc_failed_{date_dash}: {str(e)}")
        
        # 4. 汇总结果
        total_found = sum(r.get("found", 0) for r in all_results)
        total_updated = sum(r.get("updated", 0) for r in all_results)
        total_skipped = sum(r.get("skipped", 0) for r in all_results)
        
        result = {
            "message": "增强价格同步完成",
            "dates_processed": len(missing_by_date),
            "total_found": total_found,
            "total_updated": total_updated,
            "total_skipped": total_skipped,
            "used_dates_uniq": sorted(list(all_used_dates)),
            "missing_summary": {date: len(codes) for date, codes in missing_by_date.items()},
            "details": all_results,
            "recalc_performed": recalc
        }
        
        log.set_after(result)
        log.write("OK")
        return result
        
    except Exception as e:
        error_msg = f"增强价格同步失败: {str(e)}"
        log.write("ERROR", error_msg)
        return {
            "message": error_msg,
            "dates_processed": 0,
            "total_found": 0,
            "total_updated": 0,
            "total_skipped": 0,
            "error": str(e)
        }

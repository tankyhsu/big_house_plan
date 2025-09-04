from typing import Optional, List
from ..logs import LogContext
from .config_svc import get_config
from ..providers.tushare_provider import TuShareProvider
from .pricing_orchestrator import sync_prices as orchestrate

def sync_prices_tushare(
    trade_date: str,
    log: LogContext,
    ts_codes: Optional[List[str]] = None,
    fund_rate_per_min: Optional[int] = None,
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
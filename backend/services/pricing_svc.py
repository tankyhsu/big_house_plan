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
    """Thin delegator: build TuShareProvider and call orchestrator."""
    cfg = get_config()
    token = cfg.get("tushare_token")
    print(f"[sync_prices] start trade_date={trade_date}, token_present={bool(token)}")
    if not token:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_token"}
        log.set_after(info); log.write("DEBUG", "[sync_prices] no_token")
        print(f"[sync_prices] no_token -> return {info}")
        return info
    # Default rate from config when not explicitly passed
    if fund_rate_per_min is None:
        try:
            v = int(cfg.get("tushare_fund_rate_per_min", 0) or 0)
            fund_rate_per_min = v if v > 0 else None
        except Exception:
            fund_rate_per_min = None
    provider = TuShareProvider(token, fund_rate_per_min=fund_rate_per_min)
    return orchestrate(trade_date, provider, log, ts_codes)

# --- Thin delegator (new implementation) ---
from ..providers.tushare_provider import TuShareProvider as _TuShareProvider
from .pricing_orchestrator import sync_prices as _orchestrate

def sync_prices_tushare(trade_date: str, log: LogContext, ts_codes: Optional[List[str]] = None, fund_rate_per_min: Optional[int] = None) -> dict:  # type: ignore[override]
    cfg = get_config()
    token = cfg.get("tushare_token")
    print(f"[sync_prices] start trade_date={trade_date}, token_present={bool(token)}")
    if not token:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_token"}
        log.set_after(info); log.write("DEBUG", "[sync_prices] no_token")
        print(f"[sync_prices] no_token -> return {info}")
        return info
    provider = _TuShareProvider(token, fund_rate_per_min=fund_rate_per_min)
    return _orchestrate(trade_date, provider, log, ts_codes)

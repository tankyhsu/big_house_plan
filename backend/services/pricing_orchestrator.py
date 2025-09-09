from __future__ import annotations
from ..db import get_conn
from ..logs import LogContext
from ..repository import instrument_repo, price_repo
from .utils import yyyyMMdd_to_dash


class PriceProviderPort:
    def daily_for_date(self, date_yyyymmdd: str): ...
    def trade_cal_is_open(self, date_yyyymmdd: str) -> bool | None: ...
    def trade_cal_backfill_recent_open(self, end_yyyymmdd: str, lookback_days: int = 30) -> str | None: ...
    def fund_daily_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str): ...
    def fund_nav_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str): ...


def sync_prices(date_yyyymmdd: str, provider: PriceProviderPort, log: LogContext, ts_codes: list[str | None] = None) -> dict:
    trade_date = date_yyyymmdd
    used_dates: dict[str, str] = {}
    total_found = total_updated = total_skipped = 0

    # Resolve targets + types
    with get_conn() as conn:
        if ts_codes:
            tmap = instrument_repo.type_map_for(conn, ts_codes)
            all_targets = [(code, (tmap.get(code, "") or "").upper()) for code in ts_codes]
        else:
            # 获取活跃的instrument标的
            rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE active=1").fetchall()
            active_targets = [(r["ts_code"], (r["t"] or "").upper()) for r in rows]
            
            # 获取自选标的（需要连接instrument表获取type信息）
            watchlist_rows = conn.execute("""
                SELECT w.ts_code, COALESCE(i.type,'') AS t 
                FROM watchlist w 
                LEFT JOIN instrument i ON i.ts_code = w.ts_code 
                WHERE i.active = 1
            """).fetchall()
            watchlist_targets = [(r["ts_code"], (r["t"] or "").upper()) for r in watchlist_rows]
            
            # 合并并去重
            all_codes = set()
            all_targets = []
            for code, t in active_targets + watchlist_targets:
                if code not in all_codes:
                    all_codes.add(code)
                    all_targets.append((code, t))

    if not all_targets:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_active_codes"}
        log.set_after(info)
        return info

    stock_like: list[str] = []
    hk_like: list[str] = []
    etf_like: list[str] = []
    fund_like: list[str] = []
    for code, t in all_targets:
        if t == "CASH":
            continue
        if t == "ETF" or "ETF" in t:
            etf_like.append(code)
        elif t in ("FUND", "FUND_OPEN", "MUTUAL"):
            fund_like.append(code)
        elif t in ("HK", "HK_STOCK", "HONGKONG"):
            hk_like.append(code)
        else:
            stock_like.append(code)

    # Pre-filter: if we already have a price row for this exact date, skip fetching for that code
    # This reduces network calls significantly when re-running backfills.
    if stock_like or hk_like or etf_like or fund_like:
        date_dash = yyyyMMdd_to_dash(trade_date)
        with get_conn() as conn:
            pools: list[str] = list(set(stock_like + hk_like + etf_like + fund_like))
            if pools:
                placeholders = ",".join(["?"] * len(pools))
                rows = conn.execute(
                    f"SELECT DISTINCT ts_code FROM price_eod WHERE trade_date=? AND ts_code IN ({placeholders})",
                    (date_dash, *pools),
                ).fetchall()
                have = {r["ts_code"] for r in rows}
                before_counts = (len(stock_like), len(hk_like), len(etf_like), len(fund_like))
                skipped_codes = [c for c in pools if c in have]
                stock_like = [c for c in stock_like if c not in have]
                hk_like = [c for c in hk_like if c not in have]
                etf_like = [c for c in etf_like if c not in have]
                fund_like = [c for c in fund_like if c not in have]
                after_counts = (len(stock_like), len(hk_like), len(etf_like), len(fund_like))
                total_skipped += (
                    (before_counts[0] - after_counts[0]) +
                    (before_counts[1] - after_counts[1]) +
                    (before_counts[2] - after_counts[2]) +
                    (before_counts[3] - after_counts[3])
                )
                # Skip printing existing codes debug info

    # Store updated codes for ZIG signal processing
    updated_codes = []

    # STOCK: use daily with trade_cal fallback
    if stock_like:
        used_date_stock = trade_date
        df = provider.daily_for_date(trade_date)
        if df is None or df.empty:
            is_open = provider.trade_cal_is_open(trade_date)
            need_backfill = (is_open is None) or (is_open is False)
            if need_backfill:
                back = provider.trade_cal_backfill_recent_open(trade_date, lookback_days=30)
                if back:
                    used_date_stock = back
                    tmp = provider.daily_for_date(used_date_stock)
                    if tmp is not None and not tmp.empty:
                        df = tmp
        if df is not None and not df.empty:
            df = df[df["ts_code"].isin(stock_like)]
            total_found += len(df)
            bars = []
            for _, r in df.iterrows():
                bars.append({
                    "ts_code": r["ts_code"],
                    "trade_date": yyyyMMdd_to_dash(used_date_stock),
                    "close": float(r["close"]) if r["close"] is not None else None,
                    "pre_close": float(r.get("pre_close")) if "pre_close" in r and r["pre_close"] is not None else None,
                    "open": float(r["open"]) if r["open"] is not None else None,
                    "high": float(r["high"]) if r["high"] is not None else None,
                    "low": float(r["low"]) if r["low"] is not None else None,
                    "vol": float(r["vol"]) if r["vol"] is not None else None,
                    "amount": float(r["amount"]) if r["amount"] is not None else None,
                })
                used_dates[r["ts_code"]] = used_date_stock
                updated_codes.append(r["ts_code"])  # 记录更新的股票代码
            with get_conn() as conn:
                price_repo.upsert_price_eod_many(conn, bars)
            total_updated += len(bars)

    # HK STOCK: hk_daily with simple window backfill
    if hk_like:
        used_date_hk = trade_date
        dfhk = None
        try:
            # Try direct trade_date fetch for all HK
            dfhk = provider.hk_daily_for_date(trade_date)
        except Exception:
            dfhk = None
        bars: list[dict] = []
        if dfhk is not None and not dfhk.empty:
            # Filter by our codes
            try:
                dfhk2 = dfhk[dfhk["ts_code"].isin(hk_like)]
            except Exception:
                dfhk2 = dfhk
            total_found += len(dfhk2)
            for _, r in dfhk2.iterrows():
                bars.append({
                    "ts_code": r.get("ts_code") or r.get("code"),
                    "trade_date": yyyyMMdd_to_dash(str(r.get("trade_date"))),
                    "close": float(r.get("close")) if r.get("close") is not None else None,
                    "pre_close": float(r.get("pre_close")) if r.get("pre_close") is not None else None,
                    "open": float(r.get("open")) if r.get("open") is not None else None,
                    "high": float(r.get("high")) if r.get("high") is not None else None,
                    "low": float(r.get("low")) if r.get("low") is not None else None,
                    "vol": float(r.get("vol")) if r.get("vol") is not None else None,
                    "amount": float(r.get("amount")) if r.get("amount") is not None else None,
                })
                used_dates[bars[-1]["ts_code"]] = trade_date
                updated_codes.append(bars[-1]["ts_code"])  # 用于ZIG信号刷新
        else:
            # Fallback: fetch per-code window and take last <= end
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(trade_date, "%Y%m%d")
            start_dt = end_dt - timedelta(days=30)
            start_str = start_dt.strftime("%Y%m%d")
            end_str = trade_date
            for code in hk_like:
                hk_df = None
                try:
                    hk_df = provider.hk_daily_window(code, start_str, end_str)
                except Exception:
                    hk_df = None
                if hk_df is None or hk_df.empty:
                    continue
                try:
                    hk_df = hk_df.sort_values("trade_date")
                    hk_df = hk_df[hk_df["trade_date"] <= end_str]
                except Exception:
                    pass
                if hk_df is None or hk_df.empty:
                    continue
                last = hk_df.iloc[-1]
                used = str(last.get("trade_date"))
                close = last.get("close")
                if close is None:
                    continue
                bars.append({
                    "ts_code": code,
                    "trade_date": yyyyMMdd_to_dash(used),
                    "close": float(close),
                    "pre_close": float(last.get("pre_close")) if last.get("pre_close") is not None else None,
                    "open": float(last.get("open")) if last.get("open") is not None else None,
                    "high": float(last.get("high")) if last.get("high") is not None else None,
                    "low": float(last.get("low")) if last.get("low") is not None else None,
                    "vol": float(last.get("vol")) if last.get("vol") is not None else None,
                    "amount": float(last.get("amount")) if last.get("amount") is not None else None,
                })
                used_dates[code] = used
                updated_codes.append(code)
        if bars:
            with get_conn() as conn:
                price_repo.upsert_price_eod_many(conn, bars)
            total_found += len(bars)
            total_updated += len(bars)

    # ETF: fund_daily window, pick last <= end
    if etf_like:
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(trade_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=30)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = trade_date
        bars = []
        for code in etf_like:
            etf_df = provider.fund_daily_window(code, start_str, end_str)
            if etf_df is None or etf_df.empty:
                continue
            etf_df = etf_df.sort_values("trade_date")
            etf_df = etf_df[etf_df["trade_date"] <= end_str]
            if etf_df.empty:
                continue
            last = etf_df.iloc[-1]
            used_date = str(last["trade_date"])
            close = last.get("close")
            if close is None:
                continue
            bars.append({
                "ts_code": code,
                "trade_date": yyyyMMdd_to_dash(used_date),
                "close": float(close),
                "pre_close": float(last.get("pre_close")) if last.get("pre_close") is not None else None,
                "open": float(last.get("open")) if last.get("open") is not None else None,
                "high": float(last.get("high")) if last.get("high") is not None else None,
                "low": float(last.get("low")) if last.get("low") is not None else None,
                "vol": float(last.get("vol")) if last.get("vol") is not None else None,
                "amount": float(last.get("amount")) if last.get("amount") is not None else None,
            })
            used_dates[code] = used_date
            updated_codes.append(code)  # 记录更新的ETF代码
        if bars:
            with get_conn() as conn:
                price_repo.upsert_price_eod_many(conn, bars)
            total_found += len(bars)
            total_updated += len(bars)

    # FUND: fund_nav window, pick last <= end
    if fund_like:
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(trade_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=30)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = trade_date
        bars = []
        for code in fund_like:
            nav_df = provider.fund_nav_window(code, start_str, end_str)
            if nav_df is None or nav_df.empty:
                continue
            nav_df = nav_df.sort_values("nav_date")
            nav_df = nav_df[nav_df["nav_date"] <= end_str]
            if nav_df.empty:
                continue
            last = nav_df.iloc[-1]
            nav = last.get("unit_nav") or last.get("acc_nav")
            used_date = str(last["nav_date"])
            if nav is None:
                continue
            bars.append({
                "ts_code": code,
                "trade_date": yyyyMMdd_to_dash(used_date),
                "close": float(nav),
                "pre_close": None,
                "open": None,
                "high": None,
                "low": None,
                "vol": None,
                "amount": None,
            })
            used_dates[code] = used_date
            updated_codes.append(code)  # 记录更新的基金代码
        if bars:
            with get_conn() as conn:
                price_repo.upsert_price_eod_many(conn, bars)
            total_found += len(bars)
            total_updated += len(bars)

    # 如果有价格数据更新，则清理并重新生成ZIG信号
    zig_cleanup_result = None
    if updated_codes and total_updated > 0:
        try:
            from .signal_svc import TdxZigSignalGenerator
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info(f"价格同步完成，开始清理ZIG信号: {len(updated_codes)}个标的")
            
            # 调用ZIG信号清理和重新生成
            zig_cleanup_result = TdxZigSignalGenerator.cleanup_and_regenerate_zig_signals(
                yyyyMMdd_to_dash(trade_date), 
                updated_codes
            )
            
            if zig_cleanup_result and zig_cleanup_result.get("processed_instruments", 0) > 0:
                logger.info(f"ZIG信号清理完成: 处理{zig_cleanup_result['processed_instruments']}个标的，"
                          f"删除{zig_cleanup_result['deleted_signals']}个过时信号，"
                          f"生成{zig_cleanup_result['generated_signals']}个新信号")
                          
                # 将ZIG信号处理结果添加到日志
                log.set_payload({
                    "zig_signals_processed": zig_cleanup_result["processed_instruments"],
                    "zig_signals_deleted": zig_cleanup_result["deleted_signals"], 
                    "zig_signals_generated": zig_cleanup_result["generated_signals"]
                })
            
        except Exception as e:
            logger.error(f"ZIG信号清理时发生错误: {str(e)}")
            log.write("ERROR", f"ZIG信号清理失败: {str(e)}")

    result = {
        "date": trade_date,
        "found": int(total_found),
        "updated": int(total_updated),
        "skipped": int(total_skipped),
        "used_dates_uniq": sorted(list(set(used_dates.values()))) if used_dates else []
    }
    
    # 如果有ZIG信号处理结果，添加到返回结果中
    if zig_cleanup_result:
        result["zig_signals"] = {
            "processed": zig_cleanup_result["processed_instruments"],
            "deleted": zig_cleanup_result["deleted_signals"],
            "generated": zig_cleanup_result["generated_signals"]
        }
    
    log.set_after(result)
    return result

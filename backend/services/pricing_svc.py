# backend/services/pricing_svc.py
from typing import Optional, List
from ..db import get_conn
from ..logs import LogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config

# ====== Price Sync via TuShare ======
from typing import Optional, List, Tuple

def _active_non_cash_ts_codes(conn) -> List[str]:
    """
    读取启用中的标的 ts_code（剔除 type='CASH' 及空类型）
    """
    rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE active=1").fetchall()
    out = []
    for r in rows:
        if (r["t"] or "").upper() != "CASH":
            out.append(r["ts_code"])
    return out

def sync_prices_tushare(trade_date: str, log: LogContext, ts_codes: Optional[List[str]] = None, fund_rate_per_min: Optional[int] = None) -> dict:
    """
    同步指定交易日(YYYYMMDD)的市值数据，三路分流：
      - STOCK：TuShare pro.daily（股票/可交易个股）
      - ETF  ：TuShare pro.fund_daily（ETF/LOF等场内基金日线）
      - FUND ：TuShare pro.fund_nav（公募基金净值）
    取数策略：
      - STOCK：优先请求 trade_date；当日无数据（未收盘/休市）→ trade_cal 回退到最近开市日
      - ETF：在 [trade_date-30, trade_date] 区间内拉 fund_daily，取最近一条 ≤ trade_date
      - FUND：在 [trade_date-30, trade_date] 区间内拉 fund_nav，取最近一条 ≤ trade_date （unit_nav/acc_nav）
    入库策略：
      - 统一 UPSERT 到 price_eod，close=收盘价或净值
      - trade_date 统一写为 YYYY-MM-DD
    """
    from datetime import datetime, timedelta

    def _sample(lst, n=5): return list(lst[:n])

    cfg = get_config()
    token = cfg.get("tushare_token")
    print(f"[sync_prices] start trade_date={trade_date}, token_present={bool(token)}")
    if not token:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_token"}
        log.set_after(info); log.write("DEBUG", "[sync_prices] no_token")
        print(f"[sync_prices] no_token -> return {info}")
        return info

    import tushare as ts
    pro = ts.pro_api(token)
    import time

    class _RateLimiter:
        def __init__(self, max_per_min: Optional[int]):
            self.max = max_per_min if (max_per_min and max_per_min > 0) else None
            self.window_start = time.time()
            self.count = 0

        def tick(self):
            if not self.max:
                return
            now = time.time()
            elapsed = now - self.window_start
            if elapsed >= 60.0:
                self.window_start = now
                self.count = 0
            if self.count >= self.max:
                sleep_for = max(0.01, 60.0 - elapsed + 0.05)
                print(f"[sync_prices] rate-limit: sleeping {sleep_for:.2f}s to respect {self.max}/min")
                time.sleep(sleep_for)
                self.window_start = time.time()
                self.count = 0
            self.count += 1

    rate = _RateLimiter(fund_rate_per_min)

    # 读取启用标的列表 + 类型（严格按 instrument.type）
    with get_conn() as conn:
        if ts_codes:
            rows = conn.execute(
                "SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE active=1 AND ts_code IN ({})".format(
                    ",".join("?"*len(ts_codes))
                ), ts_codes
            ).fetchall()
        else:
            rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t FROM instrument WHERE active=1").fetchall()

    all_targets = [(r["ts_code"], (r["t"] or "").upper()) for r in rows]
    if not all_targets:
        info = {"date": trade_date, "found": 0, "updated": 0, "skipped": 0, "reason": "no_active_codes"}
        log.set_after(info); log.write("DEBUG", "[sync_prices] no_active_codes")
        print(f"[sync_prices] no_active_codes -> return {info}")
        return info

    # === 三类分桶 ===
    stock_like: List[str] = []
    etf_like: List[str] = []
    fund_like: List[str] = []
    for code, t in all_targets:
        tt = (t or "").upper()
        if tt == "CASH":
            continue
        # 只要类型里包含 ETF（如 ETF、ETF_INDEX、ETF_LOF 等），都归入 ETF 桶
        if tt == "ETF" or "ETF" in tt:
            etf_like.append(code)
        elif tt in ("FUND", "FUND_OPEN", "MUTUAL"):
            fund_like.append(code)
        else:
            stock_like.append(code)

    print(f"[sync_prices] classify -> stock={len(stock_like)} sample={_sample(stock_like)}; "
          f"etf={len(etf_like)} sample={_sample(etf_like)}; fund={len(fund_like)} sample={_sample(fund_like)}")

    total_found = 0
    total_updated = 0
    total_skipped = 0
    used_dates: dict = {}  # 记录每个 ts_code 实际使用的日期（YYYYMMDD）

    # ------- STOCK：pro.daily（带交易日回退）-------
    if stock_like:
        used_date_stock = trade_date
        try:
            df = pro.daily(trade_date=trade_date)
            print(f"[sync_prices] STOCK pro.daily({trade_date}) -> rows={0 if df is None else len(df)}")
        except Exception as e:
            print(f"[sync_prices] STOCK pro.daily error: {e}")
            df = None

        if df is None or df.empty:
            # 回退最近开市日（<= trade_date）
            try:
                cal = pro.trade_cal(start_date=trade_date, end_date=trade_date)
                is_open = None if (cal is None or cal.empty) else int(cal.iloc[0]["is_open"])
                print(f"[sync_prices] STOCK trade_cal({trade_date}) is_open={is_open}")
            except Exception as e:
                print(f"[sync_prices] STOCK trade_cal error: {e}")
                cal = None; is_open = None

            need_backfill = (cal is None or cal.empty or is_open == 0)
            if need_backfill:
                end = datetime.strptime(trade_date, "%Y%m%d")
                start = end - timedelta(days=30)
                try:
                    cal2 = pro.trade_cal(start_date=start.strftime("%Y%m%d"), end_date=trade_date)
                    if cal2 is not None and not cal2.empty:
                        opened = cal2[cal2["is_open"] == 1]
                        if not opened.empty:
                            used_date_stock = str(opened.iloc[-1]["cal_date"])
                    print(f"[sync_prices] STOCK backfill range=({start.strftime('%Y%m%d')}~{trade_date}) used_date={used_date_stock}")
                except Exception as e:
                    print(f"[sync_prices] STOCK trade_cal backfill error: {e}")

            if used_date_stock != trade_date:
                try:
                    tmp = pro.daily(trade_date=used_date_stock)
                    print(f"[sync_prices] STOCK retry pro.daily({used_date_stock}) -> rows={0 if tmp is None else len(tmp)}")
                    df = tmp if tmp is not None else df
                except Exception as e:
                    print(f"[sync_prices] STOCK retry daily error: {e}")

        if df is not None and not df.empty:
            before = len(df)
            df = df[df["ts_code"].isin(stock_like)]
            after = len(df)
            total_found += after
            print(f"[sync_prices] STOCK filter by targets: {before} -> {after}")
            with get_conn() as conn:
                for _, r in df.iterrows():
                    try:
                        conn.execute(
                            """
                            INSERT INTO price_eod (ts_code, trade_date, close, pre_close, open, high, low, vol, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(ts_code, trade_date) DO UPDATE SET
                                close=excluded.close,
                                pre_close=excluded.pre_close,
                                open=excluded.open,
                                high=excluded.high,
                                low=excluded.low,
                                vol=excluded.vol,
                                amount=excluded.amount
                            """,
                            (
                                r["ts_code"],
                                yyyyMMdd_to_dash(used_date_stock),
                                float(r["close"]) if r["close"] is not None else None,
                                float(r.get("pre_close")) if "pre_close" in r and r["pre_close"] is not None else None,
                                float(r["open"]) if r["open"] is not None else None,
                                float(r["high"]) if r["high"] is not None else None,
                                float(r["low"]) if r["low"] is not None else None,
                                float(r["vol"]) if r["vol"] is not None else None,
                                float(r["amount"]) if r["amount"] is not None else None,
                            ),
                        )
                        total_updated += 1
                        used_dates[r["ts_code"]] = used_date_stock
                    except Exception as e:
                        total_skipped += 1
                        print(f"[sync_prices] STOCK upsert fail ts_code={r.get('ts_code')} err={e}")
                conn.commit()
        else:
            print(f"[sync_prices] STOCK no data for date={trade_date}")

    # ------- ETF：pro.fund_daily（区间回溯，取 ≤ date 最近一条）-------
    if etf_like:
        end_dt = datetime.strptime(trade_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=30)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = trade_date
        print(f"[sync_prices] ETF using fund_daily window [{start_str} ~ {end_str}] codes={len(etf_like)}")
        with get_conn() as conn:
            for code in etf_like:
                try:
                    rate.tick()
                    # 基金日线行情（场内ETF/LOF）：close、open、high、low、vol、amount 等
                    etf_df = pro.fund_daily(ts_code=code, start_date=start_str, end_date=end_str)
                    rows_count = 0 if (etf_df is None) else len(etf_df)
                    print(f"[sync_prices] ETF fund_daily({code}) -> rows={rows_count}")
                    if etf_df is None or etf_df.empty:
                        continue

                    etf_df = etf_df.sort_values("trade_date")
                    etf_df = etf_df[etf_df["trade_date"] <= end_str]
                    if etf_df.empty:
                        continue

                    last = etf_df.iloc[-1]
                    used_date_etf = str(last["trade_date"])
                    close = last.get("close")
                    if close is None:
                        print(f"[sync_prices] ETF missing close for {code} on {used_date_etf}")
                        continue

                    conn.execute(
                        """
                        INSERT INTO price_eod (ts_code, trade_date, close, pre_close, open, high, low, vol, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ts_code, trade_date) DO UPDATE SET
                            close=excluded.close,
                            pre_close=excluded.pre_close,
                            open=excluded.open,
                            high=excluded.high,
                            low=excluded.low,
                            vol=excluded.vol,
                            amount=excluded.amount
                        """,
                        (
                            code,
                            yyyyMMdd_to_dash(used_date_etf),
                            float(close),
                            float(last.get("pre_close")) if last.get("pre_close") is not None else None,
                            float(last.get("open")) if last.get("open") is not None else None,
                            float(last.get("high")) if last.get("high") is not None else None,
                            float(last.get("low")) if last.get("low") is not None else None,
                            float(last.get("vol")) if last.get("vol") is not None else None,
                            float(last.get("amount")) if last.get("amount") is not None else None,
                        )
                    )
                    conn.commit()
                    total_found += 1
                    total_updated += 1
                    used_dates[code] = used_date_etf
                except Exception as e:
                    total_skipped += 1
                    print(f"[sync_prices] ETF upsert fail ts_code={code} err={e}")

    # ------- FUND：pro.fund_nav（区间回溯，取 ≤ date 最近一条）-------
    if fund_like:
        end_dt = datetime.strptime(trade_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=30)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = trade_date
        print(f"[sync_prices] FUND using fund_nav window [{start_str} ~ {end_str}] codes={len(fund_like)}")
        with get_conn() as conn:
            for code in fund_like:
                try:
                    rate.tick()
                    nav_df = pro.fund_nav(ts_code=code, start_date=start_str, end_date=end_str)
                    rows_count = 0 if (nav_df is None) else len(nav_df)
                    print(f"[sync_prices] FUND fund_nav({code}) -> rows={rows_count}")
                    if nav_df is None or nav_df.empty:
                        continue

                    nav_df = nav_df.sort_values("nav_date")
                    nav_df = nav_df[nav_df["nav_date"] <= end_str]
                    if nav_df.empty:
                        continue

                    last = nav_df.iloc[-1]
                    nav = last.get("unit_nav") or last.get("acc_nav")
                    used_date_fund = str(last["nav_date"])
                    if nav is None:
                        print(f"[sync_prices] FUND missing nav for {code} on {used_date_fund}")
                        continue

                    conn.execute(
                        """
                        INSERT INTO price_eod (ts_code, trade_date, close, pre_close, open, high, low, vol, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ts_code, trade_date) DO UPDATE SET
                            close=excluded.close,
                            pre_close=excluded.pre_close,
                            open=excluded.open,
                            high=excluded.high,
                            low=excluded.low,
                            vol=excluded.vol,
                            amount=excluded.amount
                        """,
                        (code, yyyyMMdd_to_dash(used_date_fund), float(nav), None, None, None, None, None, None)
                    )
                    conn.commit()
                    total_found += 1
                    total_updated += 1
                    used_dates[code] = used_date_fund
                except Exception as e:
                    total_skipped += 1
                    print(f"[sync_prices] FUND upsert fail ts_code={code} err={e}")

    # 汇总
    result = {
        "date": trade_date,
        "found": int(total_found),
        "updated": int(total_updated),
        "skipped": int(total_skipped),
        "used_dates_uniq": sorted(list(set(used_dates.values()))) if used_dates else []
    }
    log.set_after(result); log.write("DEBUG", "[sync_prices] done")
    print(f"[sync_prices] done result={result}")
    return result

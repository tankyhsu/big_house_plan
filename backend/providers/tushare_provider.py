from __future__ import annotations
from typing import Optional, Tuple, Dict, Any


class TuShareProvider:
    """Thin wrapper around tushare pro api with simple normalization + optional rate limit for fund endpoints."""

    def __init__(self, token: str, fund_rate_per_min: Optional[int] = None):
        import tushare as ts
        self.pro = ts.pro_api(token)
        import time, random
        
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
                    print(f"[tushare_provider] rate-limit: sleeping {sleep_for:.2f}s")
                    time.sleep(sleep_for)
                    self.window_start = time.time()
                    self.count = 0
                self.count += 1

        self._rate = _RateLimiter(fund_rate_per_min)
        # simple in-memory caches
        self._cache_daily: Dict[str, Any] = {}
        self._cache_trade_is_open: Dict[str, Optional[bool]] = {}
        self._cache_trade_backfill: Dict[Tuple[str, int], Optional[str]] = {}
        self._cache_fund_daily: Dict[Tuple[str, str, str], Any] = {}
        self._cache_fund_nav: Dict[Tuple[str, str, str], Any] = {}

        def _retry_call(fn, *args, tries=3, base_sleep=0.5):
            last_err = None
            for i in range(tries):
                try:
                    return fn(*args)
                except Exception as e:
                    last_err = e
                    delay = base_sleep * (2 ** i) * (1.0 + random.random() * 0.1)
                    print(f"[tushare_provider] retry {i+1}/{tries} after error: {e}; sleep {delay:.2f}s")
                    time.sleep(delay)
            print(f"[tushare_provider] failed after {tries} attempts: {last_err}")
            raise last_err

        self._retry_call = _retry_call

    # -------- STOCK --------
    def daily_for_date(self, date_yyyymmdd: str):
        if date_yyyymmdd in self._cache_daily:
            return self._cache_daily[date_yyyymmdd]
        try:
            df = self._retry_call(self.pro.daily, trade_date=date_yyyymmdd)
            self._cache_daily[date_yyyymmdd] = df
            return df
        except Exception as e:
            print(f"[tushare_provider] daily error: {e}")
            self._cache_daily[date_yyyymmdd] = None
            return None

    def trade_cal_is_open(self, date_yyyymmdd: str) -> Optional[bool]:
        if date_yyyymmdd in self._cache_trade_is_open:
            return self._cache_trade_is_open[date_yyyymmdd]
        try:
            cal = self._retry_call(self.pro.trade_cal, start_date=date_yyyymmdd, end_date=date_yyyymmdd)
            if cal is None or cal.empty:
                self._cache_trade_is_open[date_yyyymmdd] = None
                return None
            val = bool(int(cal.iloc[0]["is_open"]))
            self._cache_trade_is_open[date_yyyymmdd] = val
            return val
        except Exception as e:
            print(f"[tushare_provider] trade_cal error: {e}")
            self._cache_trade_is_open[date_yyyymmdd] = None
            return None

    def trade_cal_backfill_recent_open(self, end_yyyymmdd: str, lookback_days: int = 30) -> Optional[str]:
        from datetime import datetime, timedelta
        key = (end_yyyymmdd, int(lookback_days or 30))
        if key in self._cache_trade_backfill:
            return self._cache_trade_backfill[key]
        try:
            end = datetime.strptime(end_yyyymmdd, "%Y%m%d")
            start = end - timedelta(days=lookback_days)
            cal2 = self._retry_call(self.pro.trade_cal, start_date=start.strftime("%Y%m%d"), end_date=end_yyyymmdd)
            if cal2 is None or cal2.empty:
                self._cache_trade_backfill[key] = None
                return None
            opened = cal2[cal2["is_open"] == 1]
            if opened.empty:
                self._cache_trade_backfill[key] = None
                return None
            val = str(opened.iloc[-1]["cal_date"])
            self._cache_trade_backfill[key] = val
            return val
        except Exception as e:
            print(f"[tushare_provider] trade_cal backfill error: {e}")
            self._cache_trade_backfill[key] = None
            return None

    # -------- ETF (fund_daily) --------
    def fund_daily_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str):
        k = (ts_code, start_yyyymmdd, end_yyyymmdd)
        if k in self._cache_fund_daily:
            return self._cache_fund_daily[k]
        self._rate.tick()
        try:
            df = self._retry_call(self.pro.fund_daily, ts_code=ts_code, start_date=start_yyyymmdd, end_date=end_yyyymmdd)
            self._cache_fund_daily[k] = df
            return df
        except Exception as e:
            print(f"[tushare_provider] fund_daily error: {e}")
            self._cache_fund_daily[k] = None
            return None

    # -------- FUND (fund_nav) --------
    def fund_nav_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str):
        k = (ts_code, start_yyyymmdd, end_yyyymmdd)
        if k in self._cache_fund_nav:
            return self._cache_fund_nav[k]
        self._rate.tick()
        try:
            df = self._retry_call(self.pro.fund_nav, ts_code=ts_code, start_date=start_yyyymmdd, end_date=end_yyyymmdd)
            self._cache_fund_nav[k] = df
            return df
        except Exception as e:
            print(f"[tushare_provider] fund_nav error: {e}")
            self._cache_fund_nav[k] = None
            return None

    # -------- Basics --------
    def stock_basic_one(self, ts_code: str):
        try:
            df = self._retry_call(self.pro.stock_basic, ts_code=ts_code)
            if df is None or df.empty:
                return None
            r = df.iloc[0]
            return {"ts_code": ts_code, "name": r.get("name"), "list_date": r.get("list_date")}
        except Exception as e:
            print(f"[tushare_provider] stock_basic error: {e}")
            return None

    def fund_basic_one(self, ts_code: str):
        try:
            df = self._retry_call(self.pro.fund_basic, ts_code=ts_code)
            if df is None or df.empty:
                return None
            r = df.iloc[0]
            return {"ts_code": ts_code, "name": r.get("name"), "found_date": r.get("found_date"), "fund_type": r.get("fund_type")}
        except Exception as e:
            print(f"[tushare_provider] fund_basic error: {e}")
            return None

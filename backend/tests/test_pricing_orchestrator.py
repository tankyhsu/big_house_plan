import pandas as pd

from backend.services.pricing_orchestrator import sync_prices
from backend.db import get_conn


class DummyProvider:
    def __init__(self):
        self.calls = {}

    def daily_for_date(self, date_yyyymmdd: str):
        self.calls.setdefault("daily", []).append(date_yyyymmdd)
        # default empty
        return pd.DataFrame([])

    def trade_cal_is_open(self, date_yyyymmdd: str):
        return False

    def trade_cal_backfill_recent_open(self, end_yyyymmdd: str, lookback_days: int = 30):
        return None

    def fund_daily_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str):
        return pd.DataFrame([])

    def fund_nav_window(self, ts_code: str, start_yyyymmdd: str, end_yyyymmdd: str):
        return pd.DataFrame([])


class DummyLog:
    def set_after(self, obj):
        self.after = obj

    def write(self, result: str = "OK", err: str | None = None):
        # no-op for tests
        pass


def test_orchestrator_stock_with_fallback(tmp_db_path):
    # Prepare instrument
    with get_conn() as conn:
        conn.execute("INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)", ("c", "s", 0))
        cat_id = conn.execute("SELECT id FROM category LIMIT 1").fetchone()["id"]
        conn.execute(
            "INSERT INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,1)",
            ("AAA.STK", "AAA", "STOCK", cat_id),
        )
        conn.commit()

    prov = DummyProvider()

    # No data on target day; backfill to previous day with one quote
    def backfill(end, lookback_days=30):
        return "20250102"

    prov.trade_cal_backfill_recent_open = backfill
    prov.daily_for_date = lambda d: (
        pd.DataFrame([{"ts_code": "AAA.STK", "close": 10.5, "open": 10.0, "high": 10.6, "low": 9.9, "vol": 1000, "amount": 10000}])
        if d == "20250102"
        else pd.DataFrame([])
    )

    out = sync_prices("20250103", prov, DummyLog())
    assert "20250102" in (out.get("used_dates_uniq") or [])

    with get_conn() as conn:
        row = conn.execute(
            "SELECT trade_date, close FROM price_eod WHERE ts_code=?",
            ("AAA.STK",),
        ).fetchone()
        assert row is not None
        assert row["trade_date"] == "2025-01-02"
        assert abs(row["close"] - 10.5) < 1e-6


def test_orchestrator_etf_and_fund_windows(tmp_db_path):
    with get_conn() as conn:
        conn.execute("INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)", ("c", "s", 0))
        cat_id = conn.execute("SELECT id FROM category LIMIT 1").fetchone()["id"]
        conn.execute(
            "INSERT INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,1)",
            ("ETF1.SH", "ETF1", "ETF", cat_id),
        )
        conn.execute(
            "INSERT INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,1)",
            ("FUND1.OF", "FUND1", "FUND", cat_id),
        )
        conn.commit()

    prov = DummyProvider()
    # ETF fund_daily window returns last row at end date - 1
    prov.fund_daily_window = lambda code, s, e: (
        pd.DataFrame(
            [
                {"trade_date": "20250109", "close": 1.23, "pre_close": 1.2, "open": 1.21, "high": 1.24, "low": 1.2, "vol": 100, "amount": 1000},
            ]
        )
        if code == "ETF1.SH"
        else pd.DataFrame([])
    )
    # FUND nav window returns last nav
    prov.fund_nav_window = lambda code, s, e: (
        pd.DataFrame([
            {"nav_date": "20250110", "unit_nav": 2.34},
        ])
        if code == "FUND1.OF"
        else pd.DataFrame([])
    )

    out = sync_prices("20250110", prov, DummyLog())
    with get_conn() as conn:
        etf = conn.execute("SELECT trade_date, close FROM price_eod WHERE ts_code=?", ("ETF1.SH",)).fetchone()
        fnd = conn.execute("SELECT trade_date, close FROM price_eod WHERE ts_code=?", ("FUND1.OF",)).fetchone()
        assert etf is not None and etf["trade_date"] == "2025-01-09" and abs(etf["close"] - 1.23) < 1e-6
        assert fnd is not None and fnd["trade_date"] == "2025-01-10" and abs(fnd["close"] - 2.34) < 1e-6

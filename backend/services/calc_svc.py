# backend/services/calc_svc.py
import pandas as pd
from ..db import get_conn
from ..logs import LogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from ..repository import portfolio_repo, reporting_repo

def calc(date_yyyymmdd: str, log: LogContext):
    print("触发计算逻辑")
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config()
    unit_amount = float(cfg.get("unit_amount", 3000))
    band = float(cfg.get("overweight_band", 0.20))
    stop_gain = float(cfg.get("stop_gain_pct", 0.30))

    with get_conn() as conn:
        portfolio_repo.clear_day(conn, d)
        conn.commit()

        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)
        df = pd.DataFrame([dict(r) for r in rows])
        # Ensure required columns exist even if empty
        if df.empty:
            df = pd.DataFrame(columns=["ts_code", "category_id", "shares", "avg_cost", "close"])
        else:
            # Align column name with code below
            df.rename(columns={"eod_close": "close"}, inplace=True)
        if "close" in df.columns:
            df["close"] = df["close"].fillna(df["avg_cost"])  # fallback to avg_cost if no price
        df["market_value"] = df["shares"] * df["close"]
        df["cost"] = df["shares"] * df["avg_cost"]
        df["unrealized_pnl"] = df["market_value"] - df["cost"]
        df["ret"] = df.apply(lambda r: (r["unrealized_pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)

        for _, r in df.iterrows():
            portfolio_repo.upsert_portfolio_daily(
                conn,
                d,
                r["ts_code"],
                float(r["market_value"]),
                float(r["cost"]),
                float(r["unrealized_pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                int(r["category_id"]) if r["category_id"] is not None else None,
            )
        conn.commit()

        q2 = """
        SELECT i.category_id, SUM(pd.market_value) mv, SUM(pd.cost) cost
        FROM portfolio_daily pd JOIN instrument i ON pd.ts_code=i.ts_code
        WHERE pd.trade_date=? GROUP BY i.category_id
        """
        cat = pd.read_sql_query(q2, conn, params=(d,))
        m = pd.read_sql_query("SELECT id, target_units FROM category", conn)
        cat = cat.merge(m, left_on="category_id", right_on="id", how="left")

        cat["pnl"] = cat["mv"] - cat["cost"]
        cat["ret"] = cat.apply(lambda r: (r["pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)
        
        # 实时计算份数用于判断overweight，但不存储
        cat["actual_units"] = cat["cost"] / unit_amount
        cat["gap_units"] = cat["target_units"] - cat["actual_units"]
        def out_of_band(r):
            lower = r["target_units"] * (1 - band); upper = r["target_units"] * (1 + band)
            return 1 if (r["actual_units"] < lower or r["actual_units"] > upper) else 0
        cat["overweight"] = cat.apply(out_of_band, axis=1)

        for _, r in cat.iterrows():
            portfolio_repo.upsert_category_daily(
                conn,
                d,
                int(r["category_id"]),
                float(r["mv"]),
                float(r["cost"]),
                float(r["pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                int(r["overweight"]),
            )
            if int(r["overweight"]) == 1:
                portfolio_repo.insert_signal_category(
                    conn,
                    d,
                    int(r["category_id"]),
                    "WARN",
                    "OVERWEIGHT",
                    f"Category {r['category_id']} beyond allocation band; gap_units={r['gap_units']:.2f}",
                )

        for _, r in df.iterrows():
            if r["cost"] > 0:
                ret = r["unrealized_pnl"] / r["cost"]
                if ret is not None and ret >= stop_gain:
                    portfolio_repo.insert_signal_instrument(
                        conn,
                        d,
                        r["ts_code"],
                        "INFO",
                        "STOP_GAIN",
                        f"{r['ts_code']} return {ret:.2%} >= {stop_gain:.0%}",
                    )
        conn.commit()
    log.set_payload({"date": date_yyyymmdd})

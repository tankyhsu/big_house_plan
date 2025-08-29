# backend/services/calc_svc.py
import pandas as pd
from ..db import get_conn
from ..logs import LogContext
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config

def calc(date_yyyymmdd: str, log: LogContext):
    print("触发计算逻辑")
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config()
    unit_amount = float(cfg.get("unit_amount", 3000))
    band = float(cfg.get("overweight_band", 0.20))
    stop_gain = float(cfg.get("stop_gain_pct", 0.30))

    with get_conn() as conn:
        conn.execute("DELETE FROM portfolio_daily WHERE trade_date=?", (d,))
        conn.execute("DELETE FROM category_daily WHERE trade_date=?", (d,))
        conn.execute("DELETE FROM signal WHERE trade_date=?", (d,))
        conn.commit()

        q = """
        SELECT i.ts_code, i.category_id,
               IFNULL(p.shares,0) AS shares,
               IFNULL(p.avg_cost,0) AS avg_cost,
               (SELECT close FROM price_eod WHERE ts_code=i.ts_code AND trade_date<=? ORDER BY trade_date DESC LIMIT 1) AS close
        FROM instrument i LEFT JOIN position p ON p.ts_code=i.ts_code
        WHERE i.active=1
        """
        df = pd.read_sql_query(q, conn, params=(d,))
        df["close"] = df["close"].fillna(df["avg_cost"])
        df["market_value"] = df["shares"] * df["close"]
        df["cost"] = df["shares"] * df["avg_cost"]
        df["unrealized_pnl"] = df["market_value"] - df["cost"]
        df["ret"] = df.apply(lambda r: (r["unrealized_pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)

        for _, r in df.iterrows():
            conn.execute("""INSERT OR REPLACE INTO portfolio_daily
                (trade_date, ts_code, market_value, cost, unrealized_pnl, ret, category_id)
                VALUES (?,?,?,?,?,?,?)""",
                (d, r["ts_code"], float(r["market_value"]), float(r["cost"]),
                 float(r["unrealized_pnl"]), float(r["ret"]) if r["ret"] is not None else None,
                 int(r["category_id"]) if r["category_id"] is not None else None))
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
        cat["actual_units"] = cat["mv"] / unit_amount
        cat["gap_units"] = cat["target_units"] - cat["actual_units"]
        def out_of_band(r):
            lower = r["target_units"] * (1 - band); upper = r["target_units"] * (1 + band)
            return 1 if (r["actual_units"] < lower or r["actual_units"] > upper) else 0
        cat["overweight"] = cat.apply(out_of_band, axis=1)

        for _, r in cat.iterrows():
            conn.execute("""INSERT OR REPLACE INTO category_daily
               (trade_date, category_id, market_value, cost, pnl, ret, actual_units, gap_units, overweight)
               VALUES (?,?,?,?,?,?,?,?,?)""",
               (d, int(r["category_id"]), float(r["mv"]), float(r["cost"]), float(r["pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                float(r["actual_units"]), float(r["gap_units"]), int(r["overweight"])))
            if int(r["overweight"]) == 1:
                conn.execute("""INSERT INTO signal(trade_date, category_id, level, type, message)
                                VALUES (?,?,?,?,?)""",
                             (d, int(r["category_id"]), "WARN", "OVERWEIGHT",
                              f"Category {r['category_id']} beyond allocation band; gap_units={r['gap_units']:.2f}"))

        for _, r in df.iterrows():
            if r["cost"] > 0:
                ret = r["unrealized_pnl"] / r["cost"]
                if ret is not None and ret >= stop_gain:
                    conn.execute("""INSERT INTO signal(trade_date, ts_code, level, type, message)
                                    VALUES (?,?,?,?,?)""",
                                 (d, r["ts_code"], "INFO", "STOP_GAIN", f"{r['ts_code']} return {ret:.2%} >= {stop_gain:.0%}"))
        conn.commit()
    log.set_payload({"date": date_yyyymmdd})

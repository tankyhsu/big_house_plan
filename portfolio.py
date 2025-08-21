#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personal Portfolio System (SQLite + TuShare)

Commands:
  init                Initialize DB and seed categories/instruments/config
  add-txn             Add a transaction (buy/sell/div/fee)
  sync-prices         Pull latest EOD prices via TuShare for all active instruments
  calc                Recalculate positions, category summaries, and signals for a given date
  report              Export category/instrument summaries and signals (CSV) and print to console

Notes:
- You only need to maintain your trades via `add-txn`. Positions are materialized automatically.
- Daily prices are pulled into `price_eod`; if no price is found for a day, cost is used as fallback.
- Stop-gain and allocation-band alerts are generated into `signal` table.
"""

import argparse
import datetime as dt
import os
import sqlite3
import sys
import math

import pandas as pd
import yaml

# Optional: TuShare
try:
    import tushare as ts
except Exception:  # keep running even if tushare is not installed yet
    ts = None

# ---------------- CFG helpers ----------------

def read_cfg(path: str = "config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_conn(cfg):
    return sqlite3.connect(cfg["db_path"])  # path from config.yaml


# ---------------- Schema & Seed ----------------

def ensure_schema(conn: sqlite3.Connection):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def seed_data(conn: sqlite3.Connection):
    # seed categories
    import csv
    base = os.path.dirname(__file__)
    cats = os.path.join(base, "seeds", "categories.csv")
    with open(cats, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO category(name, sub_name, target_units)
            VALUES(?,?,?)
            """,
            (r["name"], r["sub_name"], float(r["target_units"]))
        )

    # seed instruments
    insts = os.path.join(base, "seeds", "instruments.csv")
    with open(insts, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        cur = conn.execute(
            "SELECT id FROM category WHERE name=? AND sub_name=?",
            (r["category_name"], r["category_sub_name"]),
        )
        cat = cur.fetchone()
        if not cat:
            print("[WARN] Category not found for instrument:", r, file=sys.stderr)
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO instrument(ts_code, name, type, currency, category_id, active)
            VALUES(?,?,?,?,?,1)
            """,
            (r["ts_code"], r["name"], r["type"], r["currency"], cat[0]),
        )

    # defaults in config table (if missing)
    defaults = {
        "unit_amount": "3000",
        "stop_gain_pct": "0.30",
        "overweight_band": "0.20",
        "ma_short": "20",
        "ma_long": "60",
        "ma_risk": "200",
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO config(key,value) VALUES(?,?)", (k, v))

    conn.commit()


# ---------------- Commands ----------------

def cmd_init(args):
    cfg = read_cfg(args.config)
    conn = get_conn(cfg)
    ensure_schema(conn)
    seed_data(conn)
    conn.close()
    print("DB initialized and seeded.")


def cmd_add_txn(args):
    cfg = read_cfg(args.config)
    conn = get_conn(cfg)

    action = args.action.upper()
    shares = float(args.shares)
    if action == "SELL":
        shares = -abs(shares)
    elif action in ("BUY", "DIV", "FEE", "ADJ"):
        shares = abs(shares)
    else:
        raise SystemExit("Unsupported action")

    conn.execute(
        """
        INSERT INTO txn(ts_code, trade_date, action, shares, price, amount, fee, notes)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            args.ts_code,
            args.date,
            action,
            shares,
            float(args.price or 0),
            args.amount,
            float(args.fee or 0),
            args.notes or "",
        ),
    )

    # materialized position update (average cost method)
    cur = conn.execute("SELECT shares, avg_cost FROM position WHERE ts_code=?", (args.ts_code,))
    row = cur.fetchone()
    old_shares, old_cost = (row if row else (0.0, 0.0))

    if action == "BUY":
        new_shares = old_shares + abs(shares)
        total_cost = old_shares * old_cost + abs(shares) * float(args.price or 0) + float(args.fee or 0)
        new_cost = (total_cost / new_shares) if new_shares > 0 else 0.0
        conn.execute(
            "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
            (args.ts_code, new_shares, new_cost, args.date),
        )
    elif action == "SELL":
        new_shares = round(old_shares + shares, 8)
        if new_shares < -1e-6:
            conn.rollback()
            raise SystemExit("Sell exceeds current shares")
        conn.execute(
            "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
            (args.ts_code, new_shares, old_cost if new_shares > 0 else 0.0, args.date),
        )
    # DIV/FEE/ADJ: keep it simple; extend if needed

    conn.commit()
    conn.close()
    print("Transaction added and position updated.")


def cmd_sync_prices(args):
    cfg = read_cfg(args.config)
    if ts is None:
        raise SystemExit("tushare not installed. pip install tushare")
    if not cfg.get("tushare_token") or cfg["tushare_token"].startswith("PUT_YOUR_"):
        raise SystemExit("Please set tushare_token in config.yaml")

    pro = ts.pro_api(cfg["tushare_token"])
    date = args.date or dt.datetime.now().strftime("%Y%m%d")

    conn = get_conn(cfg)
    cur = conn.execute("SELECT ts_code, type FROM instrument WHERE active=1")
    instruments = cur.fetchall()

    for ts_code, typ in instruments:
        try:
            if typ in ("etf", "fund", "stock", "bond"):
                df = pro.daily(ts_code=ts_code, start_date=date, end_date=date)
            elif typ == "cash":
                continue
            else:
                df = None

            if df is not None and len(df) > 0:
                for _, r in df.iterrows():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO price_eod
                        (ts_code, trade_date, close, pre_close, open, high, low, vol, amount)
                        VALUES(?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            r["ts_code"],
                            r["trade_date"],
                            float(r["close"]),
                            float(r.get("pre_close", 0) or 0),
                            float(r.get("open", 0) or 0),
                            float(r.get("high", 0) or 0),
                            float(r.get("low", 0) or 0),
                            float(r.get("vol", 0) or 0),
                            float(r.get("amount", 0) or 0),
                        ),
                    )
        except Exception as e:
            print(f"[WARN] fetch {ts_code} failed: {e}")

    conn.commit()
    conn.close()
    print("Prices synced for", date)


def _get_cfg_num(conn: sqlite3.Connection, key: str, default: float) -> float:
    cur = conn.execute("SELECT value FROM config WHERE key=?", (key,))
    row = cur.fetchone()
    return float(row[0]) if row else float(default)


def cmd_calc(args):
    cfg = read_cfg(args.config)
    conn = get_conn(cfg)
    date = args.date or dt.datetime.now().strftime("%Y%m%d")
    date_dash = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"

    unit_amount = _get_cfg_num(conn, "unit_amount", 3000)
    stop_gain = _get_cfg_num(conn, "stop_gain_pct", 0.30)
    band = _get_cfg_num(conn, "overweight_band", 0.20)

    # reset snapshots for the date
    conn.execute("DELETE FROM portfolio_daily WHERE trade_date=?", (date_dash,))
    conn.execute("DELETE FROM category_daily WHERE trade_date=?", (date_dash,))
    conn.execute("DELETE FROM signal WHERE trade_date=?", (date_dash,))
    conn.commit()

    # instrument-level snapshot
    q = """
    SELECT i.ts_code, i.category_id,
           IFNULL(p.shares,0) AS shares,
           IFNULL(p.avg_cost,0) AS avg_cost,
           (SELECT close FROM price_eod WHERE ts_code=i.ts_code AND trade_date=? ORDER BY trade_date DESC LIMIT 1) AS close
    FROM instrument i
    LEFT JOIN position p ON p.ts_code=i.ts_code
    WHERE i.active=1
    """
    df = pd.read_sql_query(q, conn, params=(date_dash,))
    df["close"] = df["close"].fillna(df["avg_cost"])  # fallback
    df["market_value"] = df["shares"] * df["close"]
    df["cost"] = df["shares"] * df["avg_cost"]
    df["unrealized_pnl"] = df["market_value"] - df["cost"]
    df["ret"] = df.apply(lambda r: (r["unrealized_pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)

    for _, r in df.iterrows():
        conn.execute(
            """
            INSERT OR REPLACE INTO portfolio_daily
            (trade_date, ts_code, market_value, cost, unrealized_pnl, ret, category_id)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                date_dash,
                r["ts_code"],
                float(r["market_value"]),
                float(r["cost"]),
                float(r["unrealized_pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                int(r["category_id"]) if r["category_id"] is not None else None,
            ),
        )

    conn.commit()

    # category aggregation
    q2 = """
    SELECT i.category_id, SUM(pd.market_value) mv, SUM(pd.cost) cost
    FROM portfolio_daily pd JOIN instrument i ON pd.ts_code=i.ts_code
    WHERE pd.trade_date=?
    GROUP BY i.category_id
    """
    cat = pd.read_sql_query(q2, conn, params=(date_dash,))
    m = pd.read_sql_query("SELECT id, target_units FROM category", conn)
    cat = cat.merge(m, left_on="category_id", right_on="id", how="left")
    cat["pnl"] = cat["mv"] - cat["cost"]
    cat["ret"] = cat.apply(lambda r: (r["pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)
    cat["actual_units"] = cat["mv"] / unit_amount
    cat["gap_units"] = cat["target_units"] - cat["actual_units"]

    # overweight/underweight warnings (beyond band)
    def out_of_band(r):
        lower = r["target_units"] * (1 - band)
        upper = r["target_units"] * (1 + band)
        return 1 if (r["actual_units"] < lower or r["actual_units"] > upper) else 0

    cat["overweight"] = cat.apply(out_of_band, axis=1)

    for _, r in cat.iterrows():
        conn.execute(
            """
            INSERT OR REPLACE INTO category_daily
            (trade_date, category_id, market_value, cost, pnl, ret, actual_units, gap_units, overweight)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                date_dash,
                int(r["category_id"]),
                float(r["mv"]),
                float(r["cost"]),
                float(r["pnl"]),
                float(r["ret"]) if r["ret"] is not None else None,
                float(r["actual_units"]),
                float(r["gap_units"]),
                int(r["overweight"]),
            ),
        )
        if int(r["overweight"]) == 1:
            conn.execute(
                """
                INSERT INTO signal(trade_date, category_id, level, type, message)
                VALUES (?,?,?,?,?)
                """,
                (
                    date_dash,
                    int(r["category_id"]),
                    "WARN",
                    "OVERWEIGHT",
                    f"Category {r['category_id']} beyond allocation band; gap_units={r['gap_units']:.2f}",
                ),
            )

    # stop-gain per instrument
    for _, r in df.iterrows():
        if r["cost"] > 0:
            ret = r["unrealized_pnl"] / r["cost"]
            if ret >= stop_gain:
                conn.execute(
                    """
                    INSERT INTO signal(trade_date, ts_code, level, type, message)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        date_dash,
                        r["ts_code"],
                        "INFO",
                        "STOP_GAIN",
                        f"{r['ts_code']} return {ret:.2%} >= {stop_gain:.0%}",
                    ),
                )

    conn.commit()
    conn.close()
    print("Calculation & signals done for", date_dash)


def cmd_report(args):
    cfg = read_cfg(args.config)
    conn = get_conn(cfg)
    date = args.date or dt.datetime.now().strftime("%Y%m%d")
    date_dash = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"

    cat = pd.read_sql_query(
        """
        SELECT cd.*, c.name, c.sub_name
        FROM category_daily cd JOIN category c ON cd.category_id=c.id
        WHERE cd.trade_date=?
        ORDER BY c.name, c.sub_name
        """,
        conn,
        params=(date_dash,),
    )
    ins = pd.read_sql_query(
        """
        SELECT pd.*, i.name, i.ts_code, i.category_id, c.name as cat_name, c.sub_name as cat_sub
        FROM portfolio_daily pd
        JOIN instrument i ON pd.ts_code=i.ts_code
        JOIN category c ON i.category_id=c.id
        WHERE pd.trade_date=?
        ORDER BY c.name, c.sub_name, i.ts_code
        """,
        conn,
        params=(date_dash,),
    )
    sig = pd.read_sql_query(
        "SELECT * FROM signal WHERE trade_date=? ORDER BY level DESC",
        conn,
        params=(date_dash,),
    )

    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 160)

    print("\n=== Category Summary ===")
    if not cat.empty:
        print(cat[["name", "sub_name", "market_value", "cost", "pnl", "ret", "actual_units", "gap_units", "overweight"]])
    else:
        print("(empty)")

    print("\n=== Instrument Summary ===")
    if not ins.empty:
        print(ins[["cat_name", "cat_sub", "ts_code", "name", "market_value", "cost", "unrealized_pnl", "ret"]])
    else:
        print("(empty)")

    print("\n=== Signals ===")
    if not sig.empty:
        print(sig)
    else:
        print("(none)")

    out_dir = os.path.join(os.path.dirname(__file__), "exports")
    os.makedirs(out_dir, exist_ok=True)
    cat.to_csv(os.path.join(out_dir, f"category_{date}.csv"), index=False, encoding="utf-8-sig")
    ins.to_csv(os.path.join(out_dir, f"instrument_{date}.csv"), index=False, encoding="utf-8-sig")
    sig.to_csv(os.path.join(out_dir, f"signals_{date}.csv"), index=False, encoding="utf-8-sig")

    conn.close()
    print("\nCSV exported to ./exports")


# ---------------- Entry ----------------

def main():
    parser = argparse.ArgumentParser(description="Portfolio system (SQLite + TuShare)")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers()

    p_init = sub.add_parser("init", help="init db and seed data")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add-txn", help="add a transaction")
    p_add.add_argument("--ts_code", required=True)
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_add.add_argument("--action", required=True, choices=["BUY", "SELL", "DIV", "FEE", "ADJ"])
    p_add.add_argument("--shares", required=True, type=float)
    p_add.add_argument("--price", required=False)
    p_add.add_argument("--amount", required=False)
    p_add.add_argument("--fee", required=False)
    p_add.add_argument("--notes", required=False)
    p_add.set_defaults(func=cmd_add_txn)

    p_sync = sub.add_parser("sync-prices", help="sync EOD prices from TuShare")
    p_sync.add_argument("--date", required=False, help="YYYYMMDD (default today)")
    p_sync.set_defaults(func=cmd_sync_prices)

    p_calc = sub.add_parser("calc", help="recalc positions, categories and signals")
    p_calc.add_argument("--date", required=False, help="YYYYMMDD (default today)")
    p_calc.set_defaults(func=cmd_calc)

    p_rep = sub.add_parser("report", help="export summaries and signals")
    p_rep.add_argument("--date", required=False, help="YYYYMMDD (default today)")
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

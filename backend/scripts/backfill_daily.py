#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回补每日快照（portfolio_daily / category_daily / signal）
- 默认范围：从 2020-01-01 到 今天
- 实际起算：max(2020-01-01, 最早 opening_date, 最早 txn 日期)
- 每日流程：可选同步 TuShare 价格 -> calc 重算该日快照
"""

from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from typing import Optional

# 允许脚本直接运行
if __name__ == "__main__" and __package__ is None:
    import os, sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # add backend/ to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))  # project root

from backend.db import get_conn
from backend.logs import LogContext
from backend.services.utils import yyyyMMdd_to_dash
from backend.services.calc_svc import calc
from backend.services.pricing_svc import sync_prices_tushare
# 如果你的定价/计算服务路径不同，请对应调整 import

START_DEFAULT = "20200101"

def _detect_txn_date_col(conn) -> Optional[str]:
    """探测 txn 表里用于交易日期的列名（优先级：date > trade_date > txn_date > tx_date）"""
    try:
        rows = conn.execute("PRAGMA table_info(txn)").fetchall()
        cols = { (r["name"] if isinstance(r, dict) else r[1]) for r in rows }
        for cand in ("date", "trade_date", "txn_date", "tx_date"):
            if cand in cols:
                return cand
    except Exception:
        pass
    return None

def infer_start_date() -> str:
    """推断起算日：max(20200101, min(opening_date), min(txn_date))，返回 YYYYMMDD"""
    with get_conn() as conn:
        # min opening_date（position）
        min_opening = conn.execute(
            "SELECT MIN(opening_date) AS m FROM position WHERE opening_date IS NOT NULL AND opening_date <> ''"
        ).fetchone()
        m_open = None
        if min_opening and min_opening["m"]:
            s = str(min_opening["m"])
            # 兼容 YYYYMMDD / YYYY-MM-DD
            if len(s) == 8 and s.isdigit():
                m_open = s
            elif len(s) == 10 and s[4] == "-" and s[7] == "-":
                m_open = s.replace("-", "")
        # min txn date
        col = _detect_txn_date_col(conn)
        m_txn = None
        if col:
            row = conn.execute(f"SELECT MIN({col}) AS m FROM txn").fetchone()
            if row and row["m"]:
                s = str(row["m"])
                if len(s) == 8 and s.isdigit():
                    m_txn = s
                elif len(s) == 10 and s[4] == "-" and s[7] == "-":
                    m_txn = s.replace("-", "")

    # 取有效最小值
    cands = [x for x in [m_open, m_txn] if x]
    min_exist = min(cands) if cands else None
    start = max(START_DEFAULT, min_exist) if min_exist else START_DEFAULT
    return start

def yyyymmdd_iter(start_yyyymmdd: str, end_yyyymmdd: str):
    d = datetime.strptime(start_yyyymmdd, "%Y%m%d")
    end = datetime.strptime(end_yyyymmdd, "%Y%m%d")
    while d <= end:
        yield d.strftime("%Y%m%d")
        d += timedelta(days=1)

def main():
    parser = argparse.ArgumentParser(description="回补每日快照（受建仓时间/最早交易日约束）")
    parser.add_argument("--start", help="起始日 YYYYMMDD；默认自动推断（不早于 20200101）", default=None)
    parser.add_argument("--end", help="结束日 YYYYMMDD；默认=今天", default=None)
    parser.add_argument("--sync", help="是否每日先同步 TuShare 价格", action="store_true")
    parser.add_argument("--no-sync", dest="sync", help="不做价格同步（仅用现有 price_eod）", action="store_false")
    parser.set_defaults(sync=True)
    parser.add_argument("--dry-run", help="只打印计划，不实际执行", action="store_true")
    parser.add_argument("--sleep-ms", type=int, default=0, help="每日日志之间的间隔毫秒（可用于限速）")
    parser.add_argument("--fund-rate-per-min", type=int, default=0, help="TuShare 基金相关接口限流（每分钟最大调用数，0=不限制）")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y%m%d")
    start = args.start or infer_start_date()
    end = args.end or today

    if start > end:
        print(f"[backfill] invalid range: start {start} > end {end}")
        return

    print(f"[backfill] plan: {start} -> {end} (sync={'ON' if args.sync else 'OFF'}, dry_run={args.dry_run})")

    if args.dry_run:
        total_days = sum(1 for _ in yyyymmdd_iter(start, end))
        print(f"[backfill] DRY RUN only. days={total_days}")
        return

    from time import sleep

    total = 0
    for ymd in yyyymmdd_iter(start, end):
        dash_date = yyyyMMdd_to_dash(ymd)
        print(f"[backfill] === {ymd} ({dash_date}) ===")
        try:
            if args.sync:
                log_sync = LogContext("BACKFILL_SYNC")
                res = sync_prices_tushare(ymd, log_sync, fund_rate_per_min=(args.fund_rate_per_min or None))
                print(f"[backfill] sync result: {res}")
            log_calc = LogContext("BACKFILL_CALC")
            calc(ymd, log_calc)
            print(f"[backfill] calc done for {dash_date}")
            total += 1
        except Exception as e:
            print(f"[backfill] ERROR {ymd}: {e}")
        if args.sleep_ms and args.sleep_ms > 0:
            sleep(args.sleep_ms / 1000.0)

    print(f"[backfill] finished. days_processed={total}, range={start}~{end}")

if __name__ == "__main__":
    main()

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
from backend.services.pricing_orchestrator import sync_prices as orch_sync
from backend.providers.tushare_provider import TuShareProvider
from backend.services.config_svc import get_config
# 如果你的定价/计算服务路径不同，请对应调整 import

START_DEFAULT = "20200101"

def _detect_txn_date_col(conn) -> str | None:
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
    parser.add_argument("--sleep-ms", type=int, default=100, help="每日日志之间的间隔毫秒（可用于限速）")
    parser.add_argument("--fund-rate-per-min", type=int, default=80, help="TuShare 基金相关接口限流（每分钟最大调用数，0=不限制）")
    # 按类型过滤：stock/etf/fund（可多次或逗号分隔）
    parser.add_argument("--bucket", action="append", help="按类型过滤：stock/etf/fund，可多次或逗号分隔")
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

    # 构建可复用 Provider（若配置中有 token 且需要同步）
    provider = None
    if args.sync:
        cfg = get_config()
        token = cfg.get("tushare_token")
        if token:
            rate = (args.fund_rate_per_min or None)
            try:
                if rate is None:
                    v = int(cfg.get("tushare_fund_rate_per_min", 0) or 0)
                    rate = v if v > 0 else None
            except Exception:
                rate = None
            provider = TuShareProvider(token, fund_rate_per_min=rate)
        else:
            print("[backfill] no tushare_token in config; will skip price sync and only calc")

    # 类型过滤映射为 ts_codes（若提供）
    filtered_codes = None
    if args.bucket:
        buckets: set[str] = set()
        for b in args.bucket:
            for part in str(b).split(','):
                part = (part or '').strip().lower()
                if part in {"stock", "etf", "fund"}:
                    buckets.add(part.upper())
                elif part:
                    print(f"[backfill] skip invalid bucket: {part}")
        if buckets:
            with get_conn() as conn:
                rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t, active FROM instrument").fetchall()
                codes = []
                for r in rows:
                    t = (r['t'] or '').upper()
                    if t == 'CASH':
                        continue
                    bt = 'STOCK'
                    if t == 'ETF' or 'ETF' in t:
                        bt = 'ETF'
                    elif t in ('FUND','FUND_OPEN','MUTUAL'):
                        bt = 'FUND'
                    if bt in buckets and int(r['active']) == 1:
                        codes.append(r['ts_code'])
                filtered_codes = sorted(set(codes))
                print(f"[backfill] bucket filter {sorted(buckets)} -> codes={len(filtered_codes)}")

    def codes_need_sync(date_yyyymmdd: str, base_codes: list[str | None] = None) -> list[str]:
        """Return codes that do NOT yet have a price row for the date.
        - If base_codes is None, use all active, non-CASH instruments.
        - Checks existence at exact date (not on-or-before).
        """
        date_dash = yyyyMMdd_to_dash(date_yyyymmdd)
        with get_conn() as conn:
            if base_codes is None:
                rows = conn.execute("SELECT ts_code, COALESCE(type,'') AS t, active FROM instrument").fetchall()
                base = [r['ts_code'] for r in rows if int(r['active']) == 1 and (r['t'] or '').upper() != 'CASH']
            else:
                base = list(base_codes)
            if not base:
                return []
            # Fetch codes that already have price on that date
            placeholders = ",".join(["?"] * len(base))
            have_rows = conn.execute(
                f"SELECT DISTINCT ts_code FROM price_eod WHERE trade_date=? AND ts_code IN ({placeholders})",
                (date_dash, *base),
            ).fetchall()
            have = {r['ts_code'] for r in have_rows}
            missing = [c for c in base if c not in have]
            return sorted(set(missing))

    total = 0
    for ymd in yyyymmdd_iter(start, end):
        dash_date = yyyyMMdd_to_dash(ymd)
        print(f"[backfill] === {ymd} ({dash_date}) ===")
        try:
            if args.sync and provider is not None:
                # Only sync codes that don't already have a row for this date
                target_codes = codes_need_sync(ymd, base_codes=(filtered_codes or None))
                if not target_codes:
                    print("[backfill] prices exist for all targets; skip sync")
                else:
                    log_sync = LogContext("BACKFILL_SYNC")
                    res = orch_sync(ymd, provider, log_sync, ts_codes=target_codes)
                    print(f"[backfill] sync(orch) result: {res} (requested={len(target_codes)})")
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

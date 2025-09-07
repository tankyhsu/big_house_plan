from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body

from ..logs import LogContext
from ..db import get_conn
from ..services.pricing_svc import sync_prices_tushare
from ..services.calc_svc import calc
from ..domain.txn_engine import round_price, round_quantity
from ..services.config_svc import get_config
from ..providers.tushare_provider import TuShareProvider

router = APIRouter()


class SyncBody:
    date: Optional[str] = None
    recalc: bool = False
    ts_codes: Optional[List[str]] = None
    days: Optional[int] = None


@router.post("/api/sync-prices")
def api_sync_prices(body: dict = Body(default={})):  # use raw dict for compatibility
    from datetime import datetime, timedelta

    date = body.get("date")
    recalc_flag = bool(body.get("recalc", False))
    ts_codes = body.get("ts_codes")
    days = body.get("days")

    end_date = date or datetime.now().strftime("%Y%m%d")
    dates_to_sync = [end_date]
    if days and days > 1:
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        dates_to_sync = [(end_dt - timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]

    log = LogContext("SYNC_PRICES_TUSHARE")
    log.set_payload({"dates": dates_to_sync, "ts_codes": ts_codes, "recalc": recalc_flag})

    all_results = []
    all_used_dates = set()

    try:
        for d in dates_to_sync:
            if ts_codes:
                res = sync_prices_tushare(d, LogContext(f"SYNC_{d}"), ts_codes)
            else:
                res = sync_prices_tushare(d, LogContext(f"SYNC_{d}"))
            all_results.append(res)
            used_dates = res.get("used_dates_uniq") or [d]
            all_used_dates.update(used_dates)

        log.write("OK")

        if recalc_flag:
            for d in sorted(all_used_dates):
                calc(d, LogContext("CALC_AFTER_SYNC"))

        total_found = sum(r.get("found", 0) for r in all_results)
        total_updated = sum(r.get("updated", 0) for r in all_results)
        total_skipped = sum(r.get("skipped", 0) for r in all_results)

        summary_reason = None
        if all_results and all(r.get("reason") for r in all_results):
            reasons = {r.get("reason") for r in all_results}
            if len(reasons) == 1:
                summary_reason = reasons.pop()

        response = {
            "message": "ok",
            "dates_processed": len(dates_to_sync),
            "total_found": total_found,
            "total_updated": total_updated,
            "total_skipped": total_skipped,
            "used_dates_uniq": sorted(list(all_used_dates)),
            "details": all_results,
        }
        if summary_reason:
            response["reason"] = summary_reason
        return response
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=f"sync failed: {str(e)}")


@router.get("/api/price/last")
def api_price_last(ts_code: str = Query(...), date: Optional[str] = Query(None, pattern=r"^\d{8}$")):
    from datetime import datetime as _dt
    try:
        d = date or _dt.now().strftime("%Y%m%d")
        dash = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        from ..repository.price_repo import get_last_close_on_or_before
        with get_conn() as conn:
            last = get_last_close_on_or_before(conn, ts_code, dash)
        if not last:
            return {"trade_date": None, "close": None}
        return {"trade_date": last[0], "close": float(last[1])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/price/ohlc")
def api_price_ohlc(ts_code: str = Query(...), start: str = Query(..., pattern=r"^\d{8}$"), end: str = Query(..., pattern=r"^\d{8}$")):
    try:
        sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
        ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"
        sql = (
            "SELECT trade_date, open, high, low, close, vol "
            "FROM price_eod WHERE ts_code=? AND trade_date >= ? AND trade_date <= ? "
            "ORDER BY trade_date ASC"
        )
        with get_conn() as conn:
            rows = conn.execute(sql, (ts_code, sd, ed)).fetchall()
        items = []
        for r in rows:
            c = round_price(float(r["close"])) if r["close"] is not None else None
            o = round_price(float(r["open"])) if r["open"] is not None else (c if c is not None else None)
            h = round_price(float(r["high"])) if r["high"] is not None else (c if c is not None else None)
            l = round_price(float(r["low"])) if r["low"] is not None else (c if c is not None else None)
            if c is None:
                continue
            v = round_quantity(float(r["vol"])) if ("vol" in r.keys() and r["vol"] is not None) else None
            items.append({
                "date": r["trade_date"],
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "vol": v,
            })
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/instrument/lookup")
def api_instrument_lookup(ts_code: str = Query(...), date: Optional[str] = Query(None, pattern=r"^\d{8}$")):
    cfg = get_config()
    token = cfg.get("tushare_token")
    if not token:
        raise HTTPException(status_code=400, detail="no_tushare_token")
    prov = TuShareProvider(token)
    basic = prov.fund_basic_one(ts_code) or prov.stock_basic_one(ts_code)
    out_type = None
    name = None
    if basic:
        name = basic.get("name")
        ft = (basic.get("fund_type") or "").upper()
        if ft:
            out_type = "ETF" if "ETF" in ft else "FUND"
        else:
            out_type = "STOCK"
    if not out_type:
        if ts_code.endswith(".OF"):
            out_type = "FUND"
        elif ts_code.endswith(".SH") or ts_code.endswith(".SZ"):
            out_type = "ETF"
        elif ts_code.endswith(".HK"):
            out_type = "HK"
        else:
            out_type = "STOCK"

    price = None
    if date:
        try:
            if out_type == "STOCK":
                df = prov.daily_for_date(date)
                used = date
                if df is None or df.empty:
                    back = prov.trade_cal_backfill_recent_open(date, 30)
                    if back:
                        used = back
                        df = prov.daily_for_date(used)
                if df is not None and not df.empty:
                    row = df[df["ts_code"] == ts_code]
                    if row is not None and not row.empty:
                        close = row.iloc[0].get("close")
                        if close is not None:
                            price = {"trade_date": f"{used[0:4]}-{used[4:6]}-{used[6:8]}", "close": float(close)}
            else:
                from datetime import datetime as _dt, timedelta as _td

                start_dt = _dt.strptime(date, "%Y%m%d") - _td(days=45)
                df = prov.fund_nav_window(ts_code, start_dt.strftime("%Y%m%d"), date)
                if df is not None and not df.empty:
                    df = df.sort_values("nav_date")
                    df = df[df["nav_date"] <= date]
                    if not df.empty:
                        last = df.iloc[-1]
                        nav = last.get("unit_nav") or last.get("acc_nav")
                        if nav is not None:
                            used = str(last["nav_date"])
                            price = {"trade_date": f"{used[0:4]}-{used[4:6]}-{used[6:8]}", "close": float(nav)}
        except Exception as e:
            print(f"[lookup] fetch price failed ts={ts_code} date={date}: {e}")

    return {"ts_code": ts_code, "name": name, "type": out_type, "basic": basic, "price": price}


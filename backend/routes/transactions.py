from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..logs import LogContext
from ..db import get_conn
from ..services.txn_svc import create_txn, list_txn
from ..services.calc_svc import calc
from ..domain.txn_engine import round_price, round_quantity, round_shares, round_amount

router = APIRouter()


class TxnCreate(BaseModel):
    ts_code: str
    date: str  # YYYY-MM-DD
    action: str  # BUY/SELL/DIV/FEE/ADJ
    shares: float
    price: Optional[float] = None
    amount: Optional[float] = None
    fee: Optional[float] = None
    notes: Optional[str] = None


@router.get("/api/txn/list")
def api_txn_list(page: int = 1, size: int = 20):
    total, items = list_txn(page, size)
    return {"total": total, "items": items}


@router.get("/api/txn/range")
def api_txn_range(
    start: str = Query(..., pattern=r"^\d{8}$"),
    end: str = Query(..., pattern=r"^\d{8}$"),
    ts_codes: Optional[str] = Query(None, description="逗号分隔，可选：限定标的"),
):
    try:
        sd = f"{start[0:4]}-{start[4:6]}-{start[6:8]}"
        ed = f"{end[0:4]}-{end[4:6]}-{end[6:8]}"
        codes: list[str] = []
        if ts_codes:
            codes = [c.strip() for c in ts_codes.split(",") if c and c.strip()]

        base_sql = (
            "SELECT t.trade_date AS date, t.ts_code, i.name AS name, t.action, t.shares, t.price, t.amount, t.fee "
            "FROM txn t LEFT JOIN instrument i ON i.ts_code = t.ts_code "
            "WHERE t.trade_date >= ? AND t.trade_date <= ?"
        )
        params: list[object] = [sd, ed]
        if codes:
            placeholders = ",".join(["?"] * len(codes))
            base_sql += f" AND t.ts_code IN ({placeholders})"
            params.extend(codes)
        base_sql += " ORDER BY t.trade_date ASC, t.id ASC"

        with get_conn() as conn:
            rows = conn.execute(base_sql, params).fetchall()
            items = [
                {
                    "date": r["date"],
                    "ts_code": r["ts_code"],
                    "name": r["name"],
                    "action": r["action"],
                    "shares": round_shares(float(r["shares"] or 0.0)),
                    "price": (round_price(float(r["price"])) if r["price"] is not None else None),
                    "amount": (round_amount(float(r["amount"])) if r["amount"] is not None else None),
                    "fee": (round_amount(float(r["fee"])) if r["fee"] is not None else None),
                }
                for r in rows
            ]
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/txn/create", status_code=201)
def api_txn_create(body: TxnCreate):
    log = LogContext("CREATE_TXN")
    log.set_payload(body.dict())
    try:
        res = create_txn(body.dict(), log)
        date_yyyymmdd = body.date.replace("-", "")
        calc(date_yyyymmdd, LogContext("CALC_AFTER_TXN_CREATE"))
        log.write("OK")
        return {"message": "ok", "position": res}
    except ValueError as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        log.write("ERROR", "internal error")
        raise HTTPException(status_code=500, detail="internal error")


class BulkTxnReq(BaseModel):
    items: List[TxnCreate]
    recalc: str = "latest"  # none/latest/all


@router.post("/api/txn/bulk")
def api_txn_bulk(body: BulkTxnReq):
    log = LogContext("BULK_TXN")
    log.set_payload({"count": len(body.items), "recalc": body.recalc})
    try:
        ok, fail, errs = 0, 0, []
        date_set = set()
        for i, t in enumerate(body.items):
            try:
                create_txn(t.dict(), log)
                ok += 1
                date_set.add(t.date.replace("-", ""))
            except Exception as e:
                fail += 1
                errs.append({"index": i, "ts_code": t.ts_code, "error": str(e)})

        if body.recalc != "none" and date_set:
            if body.recalc == "latest":
                calc(max(date_set), LogContext("CALC_AFTER_TXN_BULK_LATEST"))
            else:
                dates = sorted(date_set)
                if len(dates) > 50:
                    calc(dates[-1], LogContext("CALC_AFTER_TXN_BULK_GUARDED"))
                else:
                    for d in dates:
                        calc(d, LogContext("CALC_AFTER_TXN_BULK_ALL"))

        log.set_after({"ok": ok, "fail": fail})
        log.write("OK")
        return {"message": "ok", "ok": ok, "fail": fail, "errors": errs}
    except Exception as e:
        log.write("ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


import pandas as pd
from typing import List, Tuple
from .db import get_conn
from .logs import LogContext

def yyyyMMdd_to_dash(s: str) -> str:
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"

def get_config() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        cfg = {r["key"]: r["value"] for r in rows}
    # 类型转化
    def to_float(k): 
        try: return float(cfg[k])
        except: return cfg.get(k)
    out = {
        "unit_amount": to_float("unit_amount") if "unit_amount" in cfg else 3000.0,
        "stop_gain_pct": to_float("stop_gain_pct") if "stop_gain_pct" in cfg else 0.30,
        "overweight_band": to_float("overweight_band") if "overweight_band" in cfg else 0.20,
        "ma_short": int(float(cfg.get("ma_short", 20))),
        "ma_long": int(float(cfg.get("ma_long", 60))),
        "ma_risk": int(float(cfg.get("ma_risk", 200))),
        "tushare_token": cfg.get("tushare_token")
    }
    return out

def update_config(upd: dict, log: LogContext) -> List[str]:
    updated = []
    with get_conn() as conn:
        before = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config")}
        for k,v in upd.items():
            conn.execute("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
            updated.append(k)
        conn.commit()
        after = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config")}
    log.set_before(before); log.set_after(after)
    return updated

def list_txn(page:int, size:int) -> Tuple[int, List[dict]]:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(1) AS c FROM txn").fetchone()["c"]
        rows = conn.execute("""
            SELECT rowid as id, ts_code, trade_date, action, shares, price, amount, fee, notes
            FROM txn ORDER BY trade_date DESC, rowid DESC LIMIT ? OFFSET ?
        """, (size, (page-1)*size)).fetchall()
        return total, [dict(r) for r in rows]

def create_txn(data: dict, log: LogContext) -> dict:
    action = data["action"].upper()
    shares = float(data["shares"])
    fee = float(data.get("fee") or 0)
    price = float(data.get("price") or 0)
    date = data["date"]  # YYYY-MM-DD
    if action == "SELL":
        shares = -abs(shares)
    elif action in ("BUY","DIV","FEE","ADJ"):
        shares = abs(shares)
    else:
        raise ValueError("Unsupported action")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO txn(ts_code, trade_date, action, shares, price, amount, fee, notes) VALUES(?,?,?,?,?,?,?,?)",
            (data["ts_code"], date, action, shares, price, data.get("amount"), fee, data.get("notes",""))
        )
        row = conn.execute("SELECT shares, avg_cost FROM position WHERE ts_code=?", (data["ts_code"],)).fetchone()
        old_shares, old_cost = (row["shares"], row["avg_cost"]) if row else (0.0, 0.0)

        if action == "BUY":
            new_shares = old_shares + abs(shares)
            total_cost = old_shares * old_cost + abs(shares) * price + fee
            new_cost = (total_cost / new_shares) if new_shares > 0 else 0.0
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (data["ts_code"], new_shares, new_cost, date))
        elif action == "SELL":
            new_shares = round(old_shares + shares, 8)
            if new_shares < -1e-6:
                conn.rollback()
                raise ValueError("Sell exceeds current shares")
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (data["ts_code"], new_shares, old_cost if new_shares > 0 else 0.0, date))
        conn.commit()
        pos = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (data["ts_code"],)).fetchone()
    result = {"ts_code": pos["ts_code"], "shares": pos["shares"], "avg_cost": pos["avg_cost"]}
    log.set_entity("TXN", f"{cur.lastrowid}")
    log.set_after({"position": result})
    return result

def calc(date_yyyymmdd: str, log: LogContext):
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

def get_dashboard(date_yyyymmdd: str) -> dict:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        rows = conn.execute("SELECT SUM(market_value) mv, SUM(cost) cost FROM portfolio_daily WHERE trade_date=?", (d,)).fetchone()
        mv = rows["mv"] or 0.0; cost = rows["cost"] or 0.0
        pnl = mv - cost; ret = (pnl/cost) if cost>0 else None
        sig = conn.execute("SELECT type, COUNT(1) c FROM signal WHERE trade_date=? GROUP BY type", (d,)).fetchall()
        counts = {"stop_gain":0,"overweight":0}
        for r in sig:
            if r["type"] == "STOP_GAIN": counts["stop_gain"] = r["c"]
            if r["type"] == "OVERWEIGHT": counts["overweight"] = r["c"]
        used = conn.execute("""
          SELECT 1 FROM portfolio_daily pd
          JOIN instrument i ON pd.ts_code=i.ts_code
          LEFT JOIN price_eod p ON p.ts_code=pd.ts_code AND p.trade_date=?
          WHERE pd.trade_date=? AND (p.close IS NULL)
          LIMIT 1
        """, (d,d)).fetchone() is not None
    return {
        "date": d,
        "kpi": {"market_value": mv, "cost": cost, "unrealized_pnl": pnl, "ret": ret},
        "signals": {"stop_gain": counts["stop_gain"], "overweight": counts["overweight"]},
        "price_fallback_used": used
    }

def list_category(date_yyyymmdd: str) -> list[dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT cd.*, c.name, c.sub_name, c.target_units
        FROM category_daily cd JOIN category c ON cd.category_id=c.id
        WHERE cd.trade_date=? ORDER BY c.name, c.sub_name
        """, (d,)).fetchall()
    out = []
    for r in rows:
        gap = r["gap_units"]
        out.append({
            "category_id": r["category_id"],
            "name": r["name"], "sub_name": r["sub_name"],
            "target_units": r["target_units"],
            "actual_units": r["actual_units"], "gap_units": gap,
            "market_value": r["market_value"], "cost": r["cost"],
            "pnl": r["pnl"], "ret": r["ret"], "overweight": r["overweight"],
            "suggest_units": round(gap) if gap is not None else None
        })
    return out

def list_position(date_yyyymmdd: str) -> list[dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config(); stop_gain = float(cfg.get("stop_gain_pct", 0.30))
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT pd.*, i.name, i.ts_code, i.category_id, c.name as cat_name, c.sub_name as cat_sub,
               -- 取 <= 指定日的最近可用价
               (SELECT close FROM price_eod p 
                 WHERE p.ts_code=i.ts_code AND p.trade_date<=? 
                 ORDER BY p.trade_date DESC LIMIT 1) as eod_close,
               p.shares AS pos_shares, p.avg_cost AS pos_avg_cost
        FROM portfolio_daily pd
        JOIN instrument i ON pd.ts_code=i.ts_code
        JOIN category c ON i.category_id=c.id
        LEFT JOIN position p ON p.ts_code=i.ts_code
        WHERE pd.trade_date=? 
        ORDER BY c.name, c.sub_name, i.ts_code
        """, (d, d)).fetchall()

    out = []
    for r in rows:
        # 优先使用最新可用的 EOD 价；无则退回快照内的 market_value/pos_shares（兜底）
        if r["eod_close"] is not None:
            close_disp = float(r["eod_close"])
            price_source = "eod"
        else:
            close_disp = (r["market_value"]/r["pos_shares"]) if r["pos_shares"] else None
            price_source = "avg_cost_fallback" if close_disp is None else "snapshot_close"

        ret = r["ret"]
        out.append({
            "cat_name": r["cat_name"], "cat_sub": r["cat_sub"],
            "ts_code": r["ts_code"], "name": r["name"],
            "shares": r["pos_shares"], "avg_cost": r["pos_avg_cost"],
            "close": close_disp,
            "price_source": price_source,
            "market_value": r["market_value"], "cost": r["cost"],
            "unrealized_pnl": r["unrealized_pnl"], "ret": ret,
            "stop_gain_hit": (ret is not None and stop_gain is not None and ret >= stop_gain)
        })
    return out

def list_signal(date_yyyymmdd: str, typ: str|None) -> list[dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        if typ and typ.upper() != "ALL":
            rows = conn.execute("SELECT * FROM signal WHERE trade_date=? AND type=? ORDER BY level DESC", (d,typ.upper())).fetchall()
        else:
            rows = conn.execute("SELECT * FROM signal WHERE trade_date=? ORDER BY level DESC", (d,)).fetchall()
    return [dict(r) for r in rows]

def create_category(name: str, sub_name: str, target_units: float, log: LogContext) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
            (name, sub_name, float(target_units))
        )
        conn.commit()
        new_id = cur.lastrowid
    log.set_entity("CATEGORY", str(new_id))
    log.set_after({"id": new_id, "name": name, "sub_name": sub_name, "target_units": target_units})
    return new_id

def create_instrument(ts_code: str, name: str, category_id: int, active: bool, log: LogContext, sec_type: str | None = None):
    """创建/更新标的；sec_type 可为 "stock" | "eft" | "cash" 。None 时不覆盖既有值。"""
    sec_type_norm = (sec_type or "").upper().strip()
    with get_conn() as conn:
        # 读旧值（保证传 None 不会把既有 type 清空）
        old = conn.execute("SELECT type FROM instrument WHERE ts_code=?", (ts_code,)).fetchone()
        final_type = sec_type_norm if sec_type_norm else (old["type"] if old and old["type"] else None)

        if final_type is None:
            final_type = "STOCK"  # 兜底：无法判断时默认 STOCK

        conn.execute(
            "INSERT OR REPLACE INTO instrument(ts_code, name, type, category_id, active) VALUES(?,?,?,?,?)",
            (ts_code, name, final_type, int(category_id), 1 if active else 0)
        )
        conn.commit()
    log.set_entity("INSTRUMENT", ts_code)
    log.set_after({"ts_code": ts_code, "name": name, "category_id": category_id, "active": active, "type": final_type})

def set_opening_position(ts_code: str, shares: float, avg_cost: float, date: str, log: LogContext):
    """一次性设置初始持仓；之后日常变动建议用 /api/txn/create 维护"""
    with get_conn() as conn:
        # 记录before
        before = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        if before: before = dict(before)
        conn.execute(
            "INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
            (ts_code, float(shares), float(avg_cost), date)
        )
        conn.commit()
        after = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code)
    log.set_before(before)
    log.set_after(after)
    return after

def seed_load(categories_csv: str, instruments_csv: str, log: LogContext) -> dict:
    """从 CSV 导入类别与标的映射；CSV 要含必要列：
       categories.csv: name, sub_name, target_units
       instruments.csv: ts_code, name, category_name, category_sub_name, active(0/1)
       如果 instrument 指定的分类不存在，则自动创建。
    """
    cat_df = pd.read_csv(categories_csv)
    ins_df = pd.read_csv(instruments_csv)

    created_cat = 0
    created_ins = 0

    with get_conn() as conn:
        # 先建分类（若已存在则跳过）
        for _, r in cat_df.iterrows():
            name = str(r["name"]).strip()
            sub = str(r.get("sub_name", "")).strip()
            target_units = float(r["target_units"])
            row = conn.execute(
                "SELECT id FROM category WHERE name=? AND sub_name=?", (name, sub)
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
                    (name, sub, target_units)
                )
                created_cat += 1
        conn.commit()

        # 读取分类字典
        rows = conn.execute("SELECT id, name, sub_name FROM category").fetchall()
        cat_map = {(r["name"], r["sub_name"]): r["id"] for r in rows}

        # 再建标的
        for _, r in ins_df.iterrows():
            ts = str(r["ts_code"]).strip()
            nm = str(r["name"]).strip()
            cn = str(r["category_name"]).strip()
            cs = str(r.get("category_sub_name", "")).strip()
            active = int(r.get("active", 1))
            cat_id = cat_map.get((cn, cs))
            if cat_id is None:
                # 若分类不存在，自动创建
                cur = conn.execute(
                    "INSERT INTO category(name, sub_name, target_units) VALUES(?,?,?)",
                    (cn, cs, 0.0)
                )
                conn.commit()
                cat_id = cur.lastrowid
                cat_map[(cn, cs)] = cat_id
                created_cat += 1
            conn.execute(
                "INSERT OR REPLACE INTO instrument(ts_code, name, category_id, active) VALUES(?,?,?,?)",
                (ts, nm, int(cat_id), 1 if active else 0)
            )
            created_ins += 1
        conn.commit()

    log.set_after({"created_category": created_cat, "created_instrument": created_ins})
    return {"created_category": created_cat, "created_instrument": created_ins}

def bulk_txn(rows: list[dict], log: LogContext) -> dict:
    """批量写入交易（通常用于把历史BUY一次性导入作为建仓记录）"""
    ok, fail = 0, 0
    errs = []
    for i, r in enumerate(rows):
        try:
            # 复用已有 create_txn 逻辑（含均价法/卖出校验）
            create_txn(r, log)
            ok += 1
        except Exception as e:
            fail += 1
            errs.append({"index": i, "ts_code": r.get("ts_code"), "error": str(e)})
    log.set_after({"ok": ok, "fail": fail})
    return {"ok": ok, "fail": fail, "errors": errs}

# ===== Position Raw CRUD =====
from typing import Dict, Any

def list_positions_raw() -> list[dict]:
    """直接读取 position 表，联表 instrument/category 便于展示"""
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT p.ts_code, p.shares, p.avg_cost, p.last_update,
               i.name AS inst_name, i.category_id,
               c.name AS cat_name, c.sub_name AS cat_sub
        FROM position p
        LEFT JOIN instrument i ON i.ts_code = p.ts_code
        LEFT JOIN category c ON c.id = i.category_id
        ORDER BY c.name, c.sub_name, p.ts_code
        """).fetchall()
        return [dict(r) for r in rows]

def update_position_one(ts_code: str, shares: float | None, avg_cost: float | None, date: str, log: LogContext) -> dict:
    """更新一条 position 记录（部分字段可选），仅用于初始化/纠错；日常建议用交易接口"""
    with get_conn() as conn:
        before = conn.execute("SELECT ts_code, shares, avg_cost FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        if before: before = dict(before)
        if shares is None and avg_cost is None:
            raise ValueError("at least one of shares/avg_cost must be provided")
        if shares is not None and shares < 0:
            raise ValueError("shares cannot be negative")
        if before is None:
            # 新建
            conn.execute("INSERT INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (ts_code, float(shares or 0.0), float(avg_cost or 0.0), date))
        else:
            # 更新（保留未提供字段的旧值）
            new_shares = float(shares if shares is not None else before["shares"])
            new_cost = float(avg_cost if avg_cost is not None else before["avg_cost"])
            conn.execute("INSERT OR REPLACE INTO position(ts_code, shares, avg_cost, last_update) VALUES(?,?,?,?)",
                         (ts_code, new_shares, new_cost, date))
        conn.commit()
        after = conn.execute("SELECT ts_code, shares, avg_cost, last_update FROM position WHERE ts_code=?", (ts_code,)).fetchone()
        after = dict(after) if after else None
    log.set_entity("POSITION", ts_code)
    log.set_before(before)
    log.set_after(after)
    return after

# ===== Instrument List (for autocomplete) =====
from typing import Optional

def list_instruments(q: Optional[str] = None, active_only: bool = True) -> list[dict]:
    sql = """
    SELECT i.ts_code, i.name, i.active, i.category_id,
           c.name AS cat_name, c.sub_name AS cat_sub
    FROM instrument i
    LEFT JOIN category c ON c.id = i.category_id
    """
    where = []
    params = {}
    if active_only:
        where.append("i.active = 1")
    if q:
        where.append("(i.ts_code LIKE :q OR i.name LIKE :q)")
        params["q"] = f"%{q}%"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.name, c.sub_name, i.ts_code"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    
# ===== Category list for UI =====
def list_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, sub_name, target_units FROM category ORDER BY name, sub_name").fetchall()
        return [dict(r) for r in rows]

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

def sync_prices_tushare(trade_date: str, log: LogContext, ts_codes: Optional[List[str]] = None) -> dict:
    """
    同步指定交易日(YYYYMMDD)的市值数据，兼容：
      - 股票/ETF（.SH/.SZ 等）：TuShare pro.daily
      - 公募基金（.OF）：TuShare pro.fund_nav（净值）
    同步策略：
      - 股票：若当日无数据（未收盘/非交易日），回退至最近开市日（trade_cal）
      - 基金：查询 [trade_date-30, trade_date] 区间内的净值，取最近一条 ≤ trade_date
    统一写入 price_eod（close=收盘价或净值），可重复执行（UPSERT）。
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

    # 读取启用标的列表 + 类型（优先 instrument.type；无则用后缀判断）
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

    # 分类：严格按 instrument.type；不再使用代码后缀推断
    stock_like: List[str] = []
    fund_like: List[str] = []
    for code, t in all_targets:
        tt = (t or "").upper()
        if tt in ("FUND", "FUND_OPEN", "MUTUAL"):
            fund_like.append(code)
        elif tt == "CASH":
            continue  # 跳过现金
        else:
            # 其余一律按股票/ETF 处理
            stock_like.append(code)

    print(f"[sync_prices] classify -> stock_like={len(stock_like)} sample={_sample(stock_like)}; "
          f"fund_like={len(fund_like)} sample={_sample(fund_like)}")

    total_found = 0
    total_updated = 0
    total_skipped = 0
    used_dates: dict = {}  # 记录每条写入所用日期

    # ---- 股票/ETF：pro.daily + trade_cal 回退 ----
    if stock_like:
        used_date_stock = trade_date
        try:
            df = pro.daily(trade_date=trade_date)
            print(f"[sync_prices] STOCK pro.daily({trade_date}) -> rows={0 if df is None else len(df)}")
        except Exception as e:
            print(f"[sync_prices] STOCK pro.daily error: {e}")
            df = None

        if df is None or df.empty:
            # 回退到最近一个开市日
            try:
                cal = pro.trade_cal(start_date=trade_date, end_date=trade_date)
                is_open = None if (cal is None or cal.empty) else int(cal.iloc[0]["is_open"])
                print(f"[sync_prices] STOCK trade_cal({trade_date}) is_open={is_open}")
            except Exception as e:
                print(f"[sync_prices] STOCK trade_cal error: {e}")
                cal = None
                is_open = None

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
            # upsert
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
                                used_date_stock,
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

    # ---- 基金（.OF）：pro.fund_nav（净值）----
    if fund_like:
        # 对基金不走 trade_cal，直接取 30 天窗口内的最近一条净值
        end_dt = datetime.strptime(trade_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=30)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = trade_date
        print(f"[sync_prices] FUND using fund_nav window [{start_str} ~ {end_str}] codes={len(fund_like)}")

        with get_conn() as conn:
            for code in fund_like:
                try:
                    # fund_nav 支持按 ts_code 拉取区间净值
                    nav_df = pro.fund_nav(ts_code=code, start_date=start_str, end_date=end_str)
                    rows_count = 0 if (nav_df is None) else len(nav_df)
                    print(f"[sync_prices] FUND fund_nav({code}) -> rows={rows_count}")
                    if nav_df is None or nav_df.empty:
                        continue

                    # 取 ≤ trade_date 的最新一行
                    nav_df = nav_df.sort_values("nav_date")
                    nav_df = nav_df[nav_df["nav_date"] <= end_str]
                    if nav_df.empty:
                        continue

                    last = nav_df.iloc[-1]
                    nav = last.get("nav") or last.get("acc_nav")  # 优先 nav，兜底 acc_nav
                    used_date_fund = str(last["nav_date"])
                    if nav is None:
                        print(f"[sync_prices] FUND missing nav for {code} on {used_date_fund}")
                        continue

                    # upsert 到 price_eod：close=净值；其余字段置空
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
                        (code, used_date_fund, float(nav), None, None, None, None, None, None)
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
        # 用于前端友好提示：如果全部股票同一天、全部基金同一天，可以取 set(used_dates.values())
        "used_dates_uniq": sorted(list(set(used_dates.values()))) if used_dates else []
    }
    log.set_after(result); log.write("DEBUG", "[sync_prices] done")
    print(f"[sync_prices] done result={result}")
    return result
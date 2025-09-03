# backend/services/dashboard_svc.py
import pandas as pd
from typing import Optional
from ..db import get_conn
from ..repository import reporting_repo
from ..domain.txn_engine import round_price, round_quantity, round_shares, round_amount
from .utils import yyyyMMdd_to_dash
from .config_svc import get_config
from datetime import datetime, timedelta
# get_dashboard, list_category, list_position, list_signal 放这里（你已有的“动态口径”实现）

def get_dashboard(date_yyyymmdd: str) -> dict:
    """
    Dashboard KPI 动态口径：
    - 用 position（当前底仓） × price_eod 中 ≤ 指定日的最近可用价 计算市值
    - 成本 = shares × avg_cost
    - ret/pnl 动态计算；signal 仍来自快照（如未calc则可能为0）
    - price_fallback_used: 若某标的在 ≤ 指定日没有任何价格（新标的未同步），视为使用均价回退
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        # 动态聚合：每个标的取 ≤ d 最近价
        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)

        mv = 0.0; cost = 0.0; used_fallback = False
        for r in rows:
            shares = float(r["shares"] or 0.0)
            if shares <= 0: 
                continue
            avg_cost = float(r["avg_cost"] or 0.0)
            eod_close = r["eod_close"]
            if eod_close is None:
                # 没有任何 ≤ d 的价格（新标的/未同步），用均价回退并标记
                used_fallback = True
                price = avg_cost
            else:
                price = float(eod_close)
            mv += shares * price
            cost += shares * avg_cost

        pnl = mv - cost
        ret = (pnl / cost) if cost > 0 else None

        # 当日信号数量来自快照（如果未calc，可能为0）
        sig = conn.execute("SELECT type, COUNT(1) c FROM signal WHERE trade_date=? GROUP BY type", (d,)).fetchall()
        counts = {"stop_gain":0,"stop_loss":0}
        for r in sig:
            if r["type"] == "STOP_GAIN": counts["stop_gain"] = r["c"]
            if r["type"] == "STOP_LOSS": counts["stop_loss"] = r["c"]

    return {
        "date": d,
        "kpi": {"market_value": mv, "cost": cost, "unrealized_pnl": pnl, "ret": ret},
        "signals": {"stop_gain": counts["stop_gain"], "stop_loss": counts["stop_loss"]},
        "price_fallback_used": used_fallback
    }

def list_category(date_yyyymmdd: str) -> list[dict]:
    """
    类别分布动态口径（不依赖 portfolio_daily）：
    - 用 position × (≤ 指定日最近价) 动态聚合市值
    - 结合 category.target_units 计算 actual_units / gap_units / overweight
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config()
    unit_amount = float(cfg.get("unit_amount", 3000.0))
    band = float(cfg.get("overweight_band", 0.20))

    with get_conn() as conn:
        # 拉所有类别目标
        cats = pd.read_sql_query("SELECT id AS category_id, name, sub_name, target_units FROM category", conn)

        # 拉标的 + 底仓 + 最近价
        rows = reporting_repo.active_instruments_with_pos_and_price(conn, d)
        df = pd.DataFrame([dict(r) for r in rows])
        # 价格回退：无价则用均价（仅用于展示口径）
        df["price"] = df["eod_close"].fillna(df["avg_cost"])
        df["market_value"] = df["shares"] * df["price"]
        df["cost"] = df["shares"] * df["avg_cost"]

        # 按类别聚合
        agg = df.groupby("category_id", as_index=False).agg(
            market_value=("market_value", "sum"),
            cost=("cost", "sum")
        )
        agg["pnl"] = agg["market_value"] - agg["cost"]
        agg["ret"] = agg.apply(lambda r: (r["pnl"]/r["cost"]) if r["cost"]>0 else None, axis=1)
        agg = cats.merge(agg, on="category_id", how="left").fillna({"market_value":0.0, "cost":0.0, "pnl":0.0})

        # 份数/越带
        agg["actual_units"] = agg["cost"] / unit_amount
        agg["gap_units"] = agg["target_units"] - agg["actual_units"]

        def out_of_band(r):
            lower = r["target_units"] * (1 - band); upper = r["target_units"] * (1 + band)
            act = r["actual_units"]
            return 1 if (act < lower or act > upper) else 0

        agg["overweight"] = agg.apply(out_of_band, axis=1)

    # 输出
    out = []
    for _, r in agg.iterrows():
        gap = r["gap_units"]
        out.append({
            "category_id": int(r["category_id"]),
            "name": r["name"], "sub_name": r["sub_name"],
            "target_units": round_amount(float(r["target_units"])),
            "actual_units": round_amount(float(r["actual_units"])),
            "gap_units": round_amount(float(gap)),
            "market_value": round_amount(float(r["market_value"])), "cost": round_amount(float(r["cost"])),
            "pnl": round_amount(float(r["pnl"])), "ret": (round_amount(float(r["ret"])) if r["ret"]==r["ret"] else None),
            "overweight": int(r["overweight"]),
            "suggest_units": round(gap) if gap is not None else None
        })
    return out

def list_position(date_yyyymmdd: str) -> list[dict]:
    """
    标的持仓动态口径：
    - 现价优先用 ≤ 指定日最近价（eod_close）；无则回退到均价
    - 市值/收益率用动态现价计算；snapshot 值仅作兜底
    """
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    cfg = get_config(); stop_gain = float(cfg.get("stop_gain_pct", 0.30))
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT pd.*, i.name, i.ts_code, i.category_id, c.name as cat_name, c.sub_name as cat_sub,
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
        shares = float(r["pos_shares"] or 0.0)
        avg_cost = float(r["pos_avg_cost"] or 0.0)

        if r["eod_close"] is not None:
            close_disp = float(r["eod_close"])
            price_source = "eod"
        else:
            # 没有任何 ≤ d 的价格：回退均价；如 shares=0 则仍为空
            close_disp = avg_cost if shares > 0 else None
            price_source = "avg_cost_fallback" if shares > 0 else "snapshot_close"

        # 动态计算展示口径的市值/收益
        if shares > 0 and close_disp is not None:
            mv_disp = shares * close_disp
            cost_disp = shares * avg_cost
            pnl_disp = mv_disp - cost_disp
            ret_disp = (pnl_disp / cost_disp) if cost_disp > 0 else None
        else:
            # 无持仓或无价，退回快照值（通常为0）
            mv_disp = float(r["market_value"] or 0.0)
            cost_disp = float(r["cost"] or 0.0)
            pnl_disp = float(r["unrealized_pnl"] or (mv_disp - cost_disp))
            ret_disp = r["ret"]

        out.append({
            "cat_name": r["cat_name"], "cat_sub": r["cat_sub"],
            "ts_code": r["ts_code"], "name": r["name"],
            "shares": shares, "avg_cost": avg_cost,
            "close": close_disp, "price_source": price_source,
            "market_value": mv_disp, "cost": cost_disp,
            "unrealized_pnl": pnl_disp, "ret": ret_disp,
            "stop_gain_hit": (ret_disp is not None and stop_gain is not None and ret_disp >= stop_gain)
        })
    return out

def list_signal(date_yyyymmdd: str, typ: Optional[str] = None, ts_code: Optional[str] = None) -> list[dict]:
    d = yyyyMMdd_to_dash(date_yyyymmdd)
    with get_conn() as conn:
        if ts_code:
            # 查询特定标的在指定日期的信号，包括全局信号
            inst_info = conn.execute("SELECT ts_code, name, category_id, active FROM instrument WHERE ts_code=?", (ts_code,)).fetchone()
            if not inst_info:
                return []  # 标的不存在
            
            category_id = inst_info[2] if len(inst_info) > 2 else None
            
            sql = """
            SELECT DISTINCT s.* 
            FROM signal s 
            WHERE s.trade_date = ? AND (
                -- 直接匹配的信号
                s.ts_code = ?
                -- ALL_INSTRUMENTS类型信号（当该标的是激活状态时）
                OR (s.scope_type = 'ALL_INSTRUMENTS' AND ? IN (SELECT ts_code FROM instrument WHERE active=1))
                -- MULTI_INSTRUMENT类型且scope_data包含该标的
                OR (s.scope_type = 'MULTI_INSTRUMENT' AND s.scope_data IS NOT NULL AND json_extract(s.scope_data, '$') LIKE '%' || ? || '%')
            """
            params = [d, ts_code, ts_code, ts_code]
            
            # 如果标的有类别，还要包括类别相关的信号
            if category_id:
                sql += """
                    -- ALL_CATEGORIES类型信号
                    OR s.scope_type = 'ALL_CATEGORIES'
                    -- CATEGORY类型直接匹配
                    OR (s.scope_type = 'CATEGORY' AND s.category_id = ?)
                    -- MULTI_CATEGORY类型且scope_data包含该类别
                    OR (s.scope_type = 'MULTI_CATEGORY' AND s.scope_data IS NOT NULL AND json_extract(s.scope_data, '$') LIKE '%' || ? || '%')
                """
                params.extend([category_id, str(category_id)])
            
            sql += ")"
        else:
            # 查询所有信号
            sql = "SELECT * FROM signal WHERE trade_date=?"
            params = [d]
        
        # 添加类型过滤
        if typ and typ.upper() != "ALL":
            sql += " AND type=?"
            params.append(typ.upper())
            
        sql += " ORDER BY level DESC, type"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]

def list_signal_all(typ: Optional[str] = None, ts_code: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    """
    获取历史信号，按日期倒序，包含标的名称
    支持日期范围筛选
    
    对于ALL_INSTRUMENTS和ALL_CATEGORIES类型的信号，动态检查是否应用于指定标的
    """
    with get_conn() as conn:
        if ts_code:
            # 查询特定标的的信号，需要包括：
            # 1. 直接针对该标的的信号 (ts_code匹配)
            # 2. ALL_INSTRUMENTS类型的信号（如果该标的是激活的）
            # 3. MULTI_INSTRUMENT类型且scope_data包含该标的的信号
            # 4. ALL_CATEGORIES类型的信号（如果该标的所属类别存在）
            # 5. CATEGORY/MULTI_CATEGORY类型且涉及该标的所属类别的信号
            
            # 先获取该标的的基本信息
            inst_info = conn.execute("SELECT ts_code, name, category_id, active FROM instrument WHERE ts_code=?", (ts_code,)).fetchone()
            if not inst_info:
                return []  # 标的不存在
            
            category_id = inst_info[2] if len(inst_info) > 2 else None
            
            sql = """
            SELECT DISTINCT s.*, i.name 
            FROM signal s 
            LEFT JOIN instrument i ON s.ts_code = i.ts_code 
            WHERE (
                -- 直接匹配的信号
                s.ts_code = ?
                -- ALL_INSTRUMENTS类型信号（当该标的是激活状态时）
                OR (s.scope_type = 'ALL_INSTRUMENTS' AND ? IN (SELECT ts_code FROM instrument WHERE active=1))
                -- MULTI_INSTRUMENT类型且scope_data包含该标的
                OR (s.scope_type = 'MULTI_INSTRUMENT' AND s.scope_data IS NOT NULL AND json_extract(s.scope_data, '$') LIKE '%' || ? || '%')
            """
            params = [ts_code, ts_code, ts_code]
            
            # 如果标的有类别，还要包括类别相关的信号
            if category_id:
                sql += """
                    -- ALL_CATEGORIES类型信号
                    OR s.scope_type = 'ALL_CATEGORIES'
                    -- CATEGORY类型直接匹配
                    OR (s.scope_type = 'CATEGORY' AND s.category_id = ?)
                    -- MULTI_CATEGORY类型且scope_data包含该类别
                    OR (s.scope_type = 'MULTI_CATEGORY' AND s.scope_data IS NOT NULL AND json_extract(s.scope_data, '$') LIKE '%' || ? || '%')
                """
                params.extend([category_id, str(category_id)])
            
            sql += ")"
            
        else:
            # 查询所有信号
            sql = """
            SELECT s.*, i.name 
            FROM signal s 
            LEFT JOIN instrument i ON s.ts_code = i.ts_code 
            WHERE 1=1
            """
            params = []
        
        # 添加其他过滤条件
        if typ and typ.upper() != "ALL":
            sql += " AND s.type=?"
            params.append(typ.upper())
            
        if start_date:
            sql += " AND s.trade_date >= ?"
            params.append(start_date)
            
        if end_date:
            sql += " AND s.trade_date <= ?"
            params.append(end_date)
            
        sql += " ORDER BY s.trade_date DESC, s.id DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _iter_dates(start_dash: str, end_dash: str) -> list[str]:
    d0 = datetime.fromisoformat(start_dash)
    d1 = datetime.fromisoformat(end_dash)
    out = []
    cur = d0
    while cur <= d1:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def aggregate_kpi(start_yyyymmdd: str, end_yyyymmdd: str, period: str = "day") -> list[dict]:
    """
    聚合区间内的 Dashboard KPI：
      - period=day：逐日
      - period=week：每周（ISO 周）末一个点（区间内该周的最后一天）
      - period=month：每月末一个点（区间内该月的最后一天）
    复用动态口径 get_dashboard，避免依赖 snapshot 完整性。
    """
    sd = yyyyMMdd_to_dash(start_yyyymmdd)
    ed = yyyyMMdd_to_dash(end_yyyymmdd)
    days = _iter_dates(sd, ed)

    p = (period or "day").lower()
    if p == "day":
        targets = days
    elif p == "week":
        # 分组到 (ISO 年, ISO 周)，取每组最后一天
        buckets = {}
        for d in days:
            dt = datetime.fromisoformat(d)
            iso = dt.isocalendar()
            key = (iso[0], iso[1])  # (year, week)
            buckets.setdefault(key, []).append(d)
        targets = [v[-1] for _, v in sorted(buckets.items())]
    else:  # month
        buckets = {}
        for d in days:
            dt = datetime.fromisoformat(d)
            key = (dt.year, dt.month)
            buckets.setdefault(key, []).append(d)
        targets = [v[-1] for _, v in sorted(buckets.items())]

    out = []
    for dash_date in targets:
        ymd = dash_date.replace("-", "")
        k = get_dashboard(ymd)
        out.append({
            "date": dash_date,
            "market_value": k["kpi"]["market_value"],
            "cost": k["kpi"]["cost"],
            "unrealized_pnl": k["kpi"]["unrealized_pnl"],
            "ret": k["kpi"]["ret"],
        })
    return out


def create_manual_signal(trade_date: str, ts_code: Optional[str], category_id: Optional[int], level: str, type: str, message: str) -> int:
    """
    手动创建信号，用于添加政策面或市场环境变化的信号（兼容性函数）
    
    Args:
        trade_date: 信号日期 YYYY-MM-DD
        ts_code: 标的代码（可选）
        category_id: 类别ID（可选）
        level: 信号级别 (HIGH/MEDIUM/LOW/INFO)
        type: 信号类型
        message: 信号描述
        
    Returns:
        signal_id: 创建的信号ID
    """
    if ts_code:
        scope_type = "INSTRUMENT"
        scope_data = [ts_code]
    elif category_id:
        scope_type = "CATEGORY" 
        scope_data = [str(category_id)]
    else:
        raise ValueError("ts_code 和 category_id 至少提供一个")
        
    return create_manual_signal_extended(
        trade_date=trade_date,
        ts_code=ts_code,
        category_id=category_id,
        scope_type=scope_type,
        scope_data=scope_data,
        level=level,
        type=type,
        message=message
    )


def create_manual_signal_extended(
    trade_date: str, 
    ts_code: Optional[str],
    category_id: Optional[int], 
    scope_type: str,
    scope_data: Optional[list[str]],
    level: str, 
    type: str, 
    message: str
) -> int:
    """
    扩展的手动信号创建功能，支持多种范围类型
    
    Args:
        trade_date: 信号日期 YYYY-MM-DD
        ts_code: 标的代码（兼容性）
        category_id: 类别ID（兼容性）
        scope_type: 范围类型 (INSTRUMENT/CATEGORY/MULTI_INSTRUMENT/MULTI_CATEGORY/ALL_INSTRUMENTS/ALL_CATEGORIES)
        scope_data: 范围数据数组
        level: 信号级别 (HIGH/MEDIUM/LOW/INFO)
        type: 信号类型
        message: 信号描述
        
    Returns:
        signal_id: 创建的信号ID
    """
    import json
    from ..repository.portfolio_repo import insert_signal_instrument, insert_signal_category
    
    # 兼容性处理：如果使用旧参数，则转换为新格式
    if ts_code and not scope_data:
        scope_type = "INSTRUMENT"
        scope_data = [ts_code]
    elif category_id and not scope_data:
        scope_type = "CATEGORY"
        scope_data = [str(category_id)]
    
    with get_conn() as conn:
        # 根据scope_type处理不同情况
        if scope_type == "ALL_INSTRUMENTS":
            # ALL_INSTRUMENTS类型不存储具体scope_data，动态获取
            scope_data = None
            
        elif scope_type == "ALL_CATEGORIES":
            # ALL_CATEGORIES类型不存储具体scope_data，动态获取
            scope_data = None
            
        elif scope_type in ["MULTI_INSTRUMENT", "INSTRUMENT"]:
            if not scope_data:
                raise ValueError("MULTI_INSTRUMENT/INSTRUMENT scope_type 需要提供 scope_data")
            # 验证所有标的代码存在
            for code in scope_data:
                existing = conn.execute("SELECT id FROM instrument WHERE ts_code=?", (code,)).fetchone()
                if not existing:
                    raise ValueError(f"标的代码 {code} 不存在")
                    
        elif scope_type in ["MULTI_CATEGORY", "CATEGORY"]:
            if not scope_data:
                raise ValueError("MULTI_CATEGORY/CATEGORY scope_type 需要提供 scope_data")
            # 验证所有类别ID存在  
            for cat_id in scope_data:
                existing = conn.execute("SELECT id FROM category WHERE id=?", (int(cat_id),)).fetchone()
                if not existing:
                    raise ValueError(f"类别ID {cat_id} 不存在")
        
        # 为兼容性保留ts_code和category_id的设置
        final_ts_code = None
        final_category_id = None
        
        if scope_type in ["INSTRUMENT", "MULTI_INSTRUMENT"]:
            # 对于标的范围，如果只有一个，设置ts_code以保持兼容性
            if scope_data and len(scope_data) == 1:
                final_ts_code = scope_data[0]
        elif scope_type in ["CATEGORY", "MULTI_CATEGORY"]:
            # 对于类别范围，如果只有一个，设置category_id以保持兼容性
            if scope_data and len(scope_data) == 1:
                final_category_id = int(scope_data[0])
        # ALL_INSTRUMENTS和ALL_CATEGORIES不设置具体的ts_code或category_id
        
        # 插入信号记录
        scope_data_json = json.dumps(scope_data) if scope_data else None
        
        sql = """
        INSERT INTO signal (trade_date, ts_code, category_id, scope_type, scope_data, level, type, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor = conn.execute(sql, (
            trade_date, 
            final_ts_code, 
            final_category_id,
            scope_type,
            scope_data_json,
            level, 
            type, 
            message
        ))
        
        signal_id = cursor.lastrowid
        conn.commit()
        
        return signal_id

from __future__ import annotations

from sqlite3 import Connection


def get_last_close_on_or_before(conn: Connection, ts_code: str, date_dash: str) -> tuple[str, float | None]:
    row = conn.execute(
        "SELECT trade_date, close FROM price_eod WHERE ts_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
        (ts_code, date_dash),
    ).fetchone()
    if not row:
        return None
    if row["close"] is None:
        return None
    return row["trade_date"], float(row["close"])  # (YYYY-MM-DD, close)


def upsert_price_eod_many(conn: Connection, bars: list[dict]):
    if not bars:
        return 0
    sql = (
        "INSERT INTO price_eod (ts_code, trade_date, close, pre_close, open, high, low, vol, amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(ts_code, trade_date) DO UPDATE SET "
        "close=excluded.close, pre_close=excluded.pre_close, open=excluded.open, high=excluded.high, "
        "low=excluded.low, vol=excluded.vol, amount=excluded.amount"
    )
    n = 0
    for b in bars:
        conn.execute(
            sql,
            (
                b.get("ts_code"),
                b.get("trade_date"),
                b.get("close"),
                b.get("pre_close"),
                b.get("open"),
                b.get("high"),
                b.get("low"),
                b.get("vol"),
                b.get("amount"),
            ),
        )
        n += 1
    conn.commit()
    return n

def find_missing_price_dates(
    conn,
    lookback_days: int = 7,
    ts_codes: list[str] = None
) -> dict[str, list[str]]:
    """
    查找过去N天中缺失价格数据的日期
    
    Args:
        conn: 数据库连接
        lookback_days: 向前查找的天数，默认7天
        ts_codes: 可选，指定要检查的标的代码列表。为空时检查所有活跃标的
        
    Returns:
        dict: {date_yyyymmdd: [missing_ts_codes]}
    """
    from datetime import datetime, timedelta
    from ..services.utils import yyyyMMdd_to_dash
    
    if ts_codes is None:
        # 获取所有活跃的非现金标的
        rows = conn.execute(
            "SELECT ts_code FROM instrument WHERE active=1 AND COALESCE(type,'') != 'CASH'"
        ).fetchall()
        all_codes = [r["ts_code"] for r in rows]
    else:
        all_codes = ts_codes
    
    if not all_codes:
        return {}
    
    # 生成过去N天的日期列表
    today = datetime.now()
    date_list = []
    for i in range(lookback_days):
        date_dt = today - timedelta(days=i + 1)  # 从昨天开始
        date_list.append(date_dt.strftime("%Y%m%d"))
    
    missing_by_date = {}
    
    for date_yyyymmdd in date_list:
        date_dash = yyyyMMdd_to_dash(date_yyyymmdd)
        
        # 检查这一天已有价格数据的标的
        placeholders = ",".join(["?"] * len(all_codes))
        have_rows = conn.execute(
            f"SELECT DISTINCT ts_code FROM price_eod WHERE trade_date=? AND ts_code IN ({placeholders})",
            (date_dash, *all_codes),
        ).fetchall()
        have_codes = {r["ts_code"] for r in have_rows}
        
        # 找出缺失的标的
        missing_codes = [code for code in all_codes if code not in have_codes]
        if missing_codes:
            missing_by_date[date_yyyymmdd] = sorted(missing_codes)
    
    return missing_by_date

def get_price_history(
    conn,
    ts_code: str,
    end_date: str,
    limit: int = None,
    start_date: str = None
) -> list[tuple]:
    """
    获取指定标的的价格历史数据
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        end_date: 结束日期 (YYYY-MM-DD)
        limit: 可选，限制返回条数
        start_date: 可选，开始日期 (YYYY-MM-DD)
        
    Returns:
        list[tuple]: [(trade_date, close, open, high, low, vol), ...]
    """
    sql = """
        SELECT trade_date, close, open, high, low, vol 
        FROM price_eod 
        WHERE ts_code = ? AND trade_date <= ?
    """
    params = [ts_code, end_date]
    
    if start_date:
        sql += " AND trade_date >= ?"
        params.append(start_date)
    
    sql += " ORDER BY trade_date DESC"
    
    if limit:
        sql += f" LIMIT {limit}"
    
    return conn.execute(sql, params).fetchall()


def get_price_closes_for_signal(
    conn,
    ts_code: str,
    end_date: str,
    days: int = 30
) -> list[tuple]:
    """
    获取用于技术信号计算的收盘价数据
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        end_date: 结束日期 (YYYY-MM-DD)
        days: 获取天数
        
    Returns:
        list[tuple]: [(trade_date, close), ...] 按时间倒序
    """
    return conn.execute("""
        SELECT trade_date, close 
        FROM price_eod 
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC 
        LIMIT ?
    """, (ts_code, end_date, days)).fetchall()


def get_ohlcv_for_signal(
    conn,
    ts_code: str,
    end_date: str,
    days: int = 30
) -> list[tuple]:
    """
    获取用于技术信号计算的OHLCV数据
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        end_date: 结束日期 (YYYY-MM-DD)
        days: 获取天数
        
    Returns:
        list[tuple]: [(trade_date, open, high, low, close, vol), ...] 按时间倒序
    """
    return conn.execute("""
        SELECT trade_date, open, high, low, close, vol
        FROM price_eod 
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC 
        LIMIT ?
    """, (ts_code, end_date, days)).fetchall()

def get_price_change_percentage(conn: Connection, ts_code: str, date_dash: str) -> float | None:
    """
    计算指定日期的涨跌幅
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        date_dash: 日期 (YYYY-MM-DD)
        
    Returns:
        float: 涨跌幅百分比，如果无法计算则返回None
    """
    # 获取当日价格数据
    current_row = conn.execute(
        "SELECT close, pre_close FROM price_eod WHERE ts_code=? AND trade_date=?",
        (ts_code, date_dash),
    ).fetchone()
    
    if not current_row or current_row["close"] is None:
        return None
    
    current_close = float(current_row["close"])
    
    # 如果有前收盘价，直接使用
    if current_row["pre_close"] is not None:
        pre_close = float(current_row["pre_close"])
        if pre_close > 0:
            return ((current_close - pre_close) / pre_close) * 100
    
    # 否则查找前一个交易日的收盘价
    prev_row = conn.execute(
        "SELECT close FROM price_eod WHERE ts_code=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1",
        (ts_code, date_dash),
    ).fetchone()
    
    if not prev_row or prev_row["close"] is None:
        return None
    
    prev_close = float(prev_row["close"])
    if prev_close > 0:
        return ((current_close - prev_close) / prev_close) * 100
    
    return None

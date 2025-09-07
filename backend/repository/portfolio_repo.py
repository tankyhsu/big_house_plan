from __future__ import annotations

from sqlite3 import Connection


def clear_day(conn: Connection, date_dash: str):
    """
    清除指定日期的投资组合快照数据
    
    用于重新计算前清理当日数据，避免重复记录
    
    Args:
        conn: 数据库连接对象
        date_dash: 日期，格式 YYYY-MM-DD
    """
    conn.execute("DELETE FROM portfolio_daily WHERE trade_date=?", (date_dash,))
    conn.execute("DELETE FROM category_daily WHERE trade_date=?", (date_dash,))


def upsert_portfolio_daily(
    conn: Connection,
    date_dash: str,
    ts_code: str,
    market_value: float,
    cost: float,
    unrealized_pnl: float,
    ret: float | None,
    category_id: int | None,
):
    """
    插入或更新单个标的的每日投资组合快照
    
    Args:
        conn: 数据库连接对象
        date_dash: 交易日期，格式 YYYY-MM-DD
        ts_code: 标的代码
        market_value: 当前市值
        cost: 持仓成本
        unrealized_pnl: 未实现盈亏
        ret: 收益率（可为空）
        category_id: 所属类别ID（可为空）
    """
    conn.execute(
        """INSERT OR REPLACE INTO portfolio_daily
               (trade_date, ts_code, market_value, cost, unrealized_pnl, ret, category_id)
               VALUES (?,?,?,?,?,?,?)""",
        (date_dash, ts_code, market_value, cost, unrealized_pnl, ret, category_id),
    )


def upsert_category_daily(
    conn: Connection,
    date_dash: str,
    category_id: int,
    market_value: float,
    cost: float,
    pnl: float,
    ret: float | None,
    overweight: int,
):
    """
    插入或更新类别的每日汇总数据
    
    Args:
        conn: 数据库连接对象
        date_dash: 交易日期，格式 YYYY-MM-DD
        category_id: 类别ID
        market_value: 类别总市值
        cost: 类别总成本
        pnl: 未实现盈亏
        ret: 收益率（可为空）
        overweight: 是否超配（1=是，0=否）
    """
    conn.execute(
        """INSERT OR REPLACE INTO category_daily
               (trade_date, category_id, market_value, cost, pnl, ret, overweight)
               VALUES (?,?,?,?,?,?,?)""",
        (date_dash, category_id, market_value, cost, pnl, ret, overweight),
    )


def insert_signal_category(conn: Connection, date_dash: str, category_id: int, level: str, typ: str, message: str):
    """
    为类别插入信号，避免重复插入相同类型的信号
    
    Args:
        conn: 数据库连接对象
        date_dash: 交易日期，格式 YYYY-MM-DD
        category_id: 类别ID
        level: 信号级别（INFO、WARN等）
        typ: 信号类型（OVERWEIGHT等）
        message: 信号消息
    """
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND category_id=? AND type=?",
        (date_dash, category_id, typ)
    ).fetchone()
    
    if not existing:
        conn.execute(
            "INSERT INTO signal(trade_date, category_id, level, type, message) VALUES (?,?,?,?,?)",
            (date_dash, category_id, level, typ, message),
        )


def insert_signal_instrument(conn: Connection, date_dash: str, ts_code: str, level: str, typ: str, message: str):
    """
    为标的插入信号，避免重复插入相同类型的信号
    
    Args:
        conn: 数据库连接对象
        date_dash: 交易日期，格式 YYYY-MM-DD
        ts_code: 标的代码
        level: 信号级别（INFO、WARN等）
        typ: 信号类型（STOP_GAIN、STOP_LOSS等）
        message: 信号消息
    """
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
        (date_dash, ts_code, typ)
    ).fetchone()
    
    if not existing:
        conn.execute(
            "INSERT INTO signal(trade_date, ts_code, level, type, message) VALUES (?,?,?,?,?)",
            (date_dash, ts_code, level, typ, message),
        )


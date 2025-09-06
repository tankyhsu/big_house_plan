"""
信号数据访问层
负责信号的数据库操作，包括查询、插入、更新等
"""

import json
from typing import Optional, List, Dict, Any
from sqlite3 import Connection

def get_signals_by_date(conn: Connection, trade_date: str, signal_type: Optional[str] = None, 
                       ts_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取指定日期的信号记录
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
        signal_type: 信号类型过滤
        ts_code: 标的代码过滤
    
    Returns:
        信号记录列表
    """
    base_sql = "SELECT * FROM signal WHERE trade_date = ?"
    params = [trade_date]
    
    if signal_type and signal_type.upper() != "ALL":
        base_sql += " AND type = ?"
        params.append(signal_type.upper())
    
    if ts_code:
        base_sql += " AND ts_code = ?"
        params.append(ts_code)
    
    base_sql += " ORDER BY level DESC, type"
    
    rows = conn.execute(base_sql, params).fetchall()
    return [dict(row) for row in rows]


def get_signals_for_instrument(conn: Connection, ts_code: str, trade_date: str) -> List[Dict[str, Any]]:
    """
    获取特定标的在指定日期的所有相关信号（包括全局信号）
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        trade_date: 交易日期 YYYY-MM-DD
    
    Returns:
        信号记录列表
    """
    # 获取标的基本信息
    inst_info = conn.execute(
        "SELECT ts_code, name, category_id, active FROM instrument WHERE ts_code=?", 
        (ts_code,)
    ).fetchone()
    
    if not inst_info:
        return []
    
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
    
    params = [trade_date, ts_code, ts_code, ts_code]
    
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
    
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_signals_history(conn: Connection, signal_type: Optional[str] = None, ts_code: Optional[str] = None,
                       start_date: Optional[str] = None, end_date: Optional[str] = None, 
                       limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取历史信号记录
    
    Args:
        conn: 数据库连接
        signal_type: 信号类型过滤
        ts_code: 标的代码过滤
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回记录数限制
    
    Returns:
        信号记录列表，包含标的名称
    """
    if ts_code:
        # 查询特定标的的信号，需要包括全局信号
        inst_info = conn.execute(
            "SELECT ts_code, name, category_id, active FROM instrument WHERE ts_code=?", 
            (ts_code,)
        ).fetchone()
        
        if not inst_info:
            return []
        
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
    if signal_type and signal_type.upper() != "ALL":
        sql += " AND s.type=?"
        params.append(signal_type.upper())
        
    if start_date:
        sql += " AND s.trade_date >= ?"
        params.append(start_date)
        
    if end_date:
        sql += " AND s.trade_date <= ?"
        params.append(end_date)
        
    sql += " ORDER BY s.trade_date DESC, s.id DESC LIMIT ?"
    params.append(limit)
    
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def insert_signal(conn: Connection, trade_date: str, ts_code: Optional[str] = None,
                 category_id: Optional[int] = None, scope_type: str = 'INSTRUMENT',
                 scope_data: Optional[List[str]] = None, level: str = 'INFO',
                 signal_type: str = 'INFO', message: str = '') -> int:
    """
    插入信号记录
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
        ts_code: 标的代码（兼容性）
        category_id: 类别ID（兼容性）
        scope_type: 范围类型
        scope_data: 范围数据
        level: 信号级别
        signal_type: 信号类型
        message: 信号消息
    
    Returns:
        创建的信号ID
    """
    # 兼容性处理：如果使用旧参数，则转换为新格式
    if ts_code and not scope_data:
        scope_type = "INSTRUMENT"
        scope_data = [ts_code]
    elif category_id and not scope_data:
        scope_type = "CATEGORY"
        scope_data = [str(category_id)]
    
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
        signal_type, 
        message
    ))
    
    return cursor.lastrowid


def insert_signal_if_not_exists(conn: Connection, trade_date: str, ts_code: str,
                               level: str, signal_type: str, message: str) -> Optional[int]:
    """
    如果信号不存在则插入信号记录（避免重复插入相同类型的信号）
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
        ts_code: 标的代码
        level: 信号级别
        signal_type: 信号类型
        message: 信号消息
    
    Returns:
        创建的信号ID，如果已存在则返回None
    """
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
        (trade_date, ts_code, signal_type)
    ).fetchone()
    
    if not existing:
        return insert_signal(conn, trade_date, ts_code=ts_code, level=level, 
                           signal_type=signal_type, message=message)
    
    return None

def has_recent_stop_signal(conn: Connection, ts_code: str, check_date: str, days_back: int = 30) -> bool:
    """
    检查指定标的在过去一段时间内是否已有止盈或止损信号
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        check_date: 检查日期 YYYY-MM-DD
        days_back: 往前检查的天数，默认30天
    
    Returns:
        True如果已有止盈/止损信号，False如果没有
    """
    from datetime import datetime, timedelta
    
    check_dt = datetime.strptime(check_date, "%Y-%m-%d")
    start_date = (check_dt - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    existing = conn.execute("""
        SELECT id FROM signal 
        WHERE ts_code = ? 
        AND trade_date >= ? 
        AND trade_date <= ? 
        AND type IN ('STOP_GAIN', 'STOP_LOSS')
        LIMIT 1
    """, (ts_code, start_date, check_date)).fetchone()
    
    return existing is not None


def has_recent_structure_signal(conn: Connection, ts_code: str, check_date: str, days_back: int = 9) -> bool:
    """
    检查指定标的在过去一段时间内是否已有九转买入/九转卖出信号
    
    Args:
        conn: 数据库连接
        ts_code: 标的代码
        check_date: 检查日期 YYYY-MM-DD
        days_back: 往前检查的天数，默认9天
    
    Returns:
        True如果已有结构信号，False如果没有
    """
    # 以交易日为基准，取从check_date往前数days_back个交易日的最早日期作为窗口起点
    # 如果过去days_back个交易日内已有结构信号，则返回True
    # 查出该标的最近days_back个交易日（含当天）
    trade_days = conn.execute(
        """
        SELECT trade_date FROM price_eod
        WHERE ts_code=? AND trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (ts_code, check_date, days_back),
    ).fetchall()
    if not trade_days:
        return False
    # 窗口起点为这些交易日中的最早一个
    start_date = trade_days[-1][0]
    existing = conn.execute(
        """
        SELECT id FROM signal 
        WHERE ts_code = ? 
          AND trade_date >= ? 
          AND trade_date <= ? 
          AND type IN ('BUY_STRUCTURE', 'SELL_STRUCTURE')
        LIMIT 1
        """,
        (ts_code, start_date, check_date),
    ).fetchone()
    return existing is not None


def insert_signal_if_no_recent_structure(
    conn: Connection,
    trade_date: str,
    ts_code: str,
    level: str,
    signal_type: str,
    message: str,
    days_back: int = 9,
) -> Optional[int]:
    """
    如果过去一段时间内没有九转买入/九转卖出信号则插入信号记录；包含同日去重。
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
        ts_code: 标的代码
        level: 信号级别
        signal_type: 信号类型（BUY_STRUCTURE/SELL_STRUCTURE）
        message: 信号消息
        days_back: 往前检查的天数，默认9天
    
    Returns:
        创建的信号ID，如果已存在或不应创建则返回None
    """
    # 结构信号过去9天内已出现则不再创建
    if signal_type in ("BUY_STRUCTURE", "SELL_STRUCTURE"):
        if has_recent_structure_signal(conn, ts_code, trade_date, days_back):
            return None

    # 当天同类型信号去重
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
        (trade_date, ts_code, signal_type),
    ).fetchone()
    if not existing:
        return insert_signal(
            conn,
            trade_date,
            ts_code=ts_code,
            level=level,
            signal_type=signal_type,
            message=message,
        )
    return None

def insert_signal_if_no_recent_stop(conn: Connection, trade_date: str, ts_code: str,
                                   level: str, signal_type: str, message: str, 
                                   days_back: int = 30) -> Optional[int]:
    """
    如果过去一段时间内没有止盈/止损信号则插入信号记录
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
        ts_code: 标的代码
        level: 信号级别
        signal_type: 信号类型
        message: 信号消息
        days_back: 往前检查的天数，默认30天
    
    Returns:
        创建的信号ID，如果已存在或不应创建则返回None
    """
    # 对于止盈/止损信号，检查过去一段时间内是否已有相同类型的信号
    if signal_type in ('STOP_GAIN', 'STOP_LOSS'):
        if has_recent_stop_signal(conn, ts_code, trade_date, days_back):
            return None
    
    # 检查当天是否已有相同信号（保持原有逻辑）
    existing = conn.execute(
        "SELECT id FROM signal WHERE trade_date=? AND ts_code=? AND type=?",
        (trade_date, ts_code, signal_type)
    ).fetchone()
    
    if not existing:
        return insert_signal(conn, trade_date, ts_code=ts_code, level=level, 
                           signal_type=signal_type, message=message)
    
    return None


def delete_signals_by_type(conn: Connection, signal_types: List[str]) -> int:
    """
    删除指定类型的所有信号
    
    Args:
        conn: 数据库连接
        signal_types: 要删除的信号类型列表
    
    Returns:
        删除的记录数
    """
    if not signal_types:
        return 0
    
    placeholders = ','.join('?' for _ in signal_types)
    result = conn.execute(f"DELETE FROM signal WHERE type IN ({placeholders})", signal_types)
    return result.rowcount


def get_signal_counts_by_date(conn: Connection, trade_date: str) -> Dict[str, int]:
    """
    获取指定日期各类型信号的统计数量
    
    Args:
        conn: 数据库连接
        trade_date: 交易日期 YYYY-MM-DD
    
    Returns:
        各信号类型的数量字典
    """
    rows = conn.execute(
        "SELECT type, COUNT(1) c FROM signal WHERE trade_date=? GROUP BY type", 
        (trade_date,)
    ).fetchall()
    
    counts = {row[0].lower(): row[1] for row in rows}
    
    # 确保所有基础类型都有值
    return {
        "stop_gain": counts.get("stop_gain", 0),
        "stop_loss": counts.get("stop_loss", 0),
    }


def validate_instrument_codes(conn: Connection, ts_codes: List[str]) -> List[str]:
    """
    验证标的代码是否存在
    
    Args:
        conn: 数据库连接
        ts_codes: 标的代码列表
    
    Returns:
        不存在的标的代码列表
    """
    if not ts_codes:
        return []
    
    placeholders = ','.join('?' for _ in ts_codes)
    existing_codes = conn.execute(
        f"SELECT ts_code FROM instrument WHERE ts_code IN ({placeholders})", 
        ts_codes
    ).fetchall()
    
    existing_set = {row[0] for row in existing_codes}
    return [code for code in ts_codes if code not in existing_set]


def validate_category_ids(conn: Connection, category_ids: List[int]) -> List[int]:
    """
    验证类别ID是否存在
    
    Args:
        conn: 数据库连接
        category_ids: 类别ID列表
    
    Returns:
        不存在的类别ID列表
    """
    if not category_ids:
        return []
    
    placeholders = ','.join('?' for _ in category_ids)
    existing_ids = conn.execute(
        f"SELECT id FROM category WHERE id IN ({placeholders})", 
        category_ids
    ).fetchall()
    
    existing_set = {row[0] for row in existing_ids}
    return [cat_id for cat_id in category_ids if cat_id not in existing_set]

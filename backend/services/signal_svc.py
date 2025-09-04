"""
信号业务服务层
负责信号相关的业务逻辑，包括信号查询、创建、历史信号生成等
"""

from typing import Optional, List, Dict, Any, Tuple
from ..db import get_conn
from ..repository import signal_repo
from .utils import yyyyMMdd_to_dash


class SignalService:
    """信号业务服务"""

    @staticmethod
    def get_signals_by_date(date_yyyymmdd: str, signal_type: Optional[str] = None, 
                           ts_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取指定日期的信号记录
        
        Args:
            date_yyyymmdd: 日期格式 YYYYMMDD
            signal_type: 信号类型过滤
            ts_code: 标的代码过滤
            
        Returns:
            信号记录列表
        """
        trade_date = yyyyMMdd_to_dash(date_yyyymmdd)
        
        with get_conn() as conn:
            if ts_code:
                # 获取特定标的的所有相关信号（包括全局信号）
                signals = signal_repo.get_signals_for_instrument(conn, ts_code, trade_date)
                
                # 如果有类型过滤，则应用过滤
                if signal_type and signal_type.upper() != "ALL":
                    signals = [s for s in signals if s.get('type') == signal_type.upper()]
                
                return signals
            else:
                # 获取所有信号
                return signal_repo.get_signals_by_date(conn, trade_date, signal_type)

    @staticmethod
    def get_signals_history(signal_type: Optional[str] = None, ts_code: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None, 
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取历史信号记录
        
        Args:
            signal_type: 信号类型过滤
            ts_code: 标的代码过滤
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回记录数限制
            
        Returns:
            信号记录列表，包含标的名称
        """
        with get_conn() as conn:
            return signal_repo.get_signals_history(
                conn, signal_type, ts_code, start_date, end_date, limit
            )

    @staticmethod
    def create_manual_signal(trade_date: str, ts_code: Optional[str] = None,
                           category_id: Optional[int] = None, scope_type: str = 'INSTRUMENT',
                           scope_data: Optional[List[str]] = None, level: str = 'INFO',
                           signal_type: str = 'INFO', message: str = '') -> int:
        """
        创建手动信号
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            ts_code: 标的代码（兼容性）
            category_id: 类别ID（兼容性）
            scope_type: 范围类型 (INSTRUMENT/CATEGORY/MULTI_INSTRUMENT/MULTI_CATEGORY/ALL_INSTRUMENTS/ALL_CATEGORIES)
            scope_data: 范围数据数组
            level: 信号级别 (HIGH/MEDIUM/LOW/INFO)
            signal_type: 信号类型
            message: 信号描述
            
        Returns:
            创建的信号ID
            
        Raises:
            ValueError: 当参数验证失败时
        """
        with get_conn() as conn:
            # 参数验证
            SignalService._validate_signal_params(
                conn, scope_type, scope_data, ts_code, category_id
            )
            
            signal_id = signal_repo.insert_signal(
                conn, trade_date, ts_code, category_id, scope_type, scope_data,
                level, signal_type, message
            )
            
            conn.commit()
            return signal_id

    @staticmethod
    def _validate_signal_params(conn, scope_type: str, scope_data: Optional[List[str]],
                               ts_code: Optional[str], category_id: Optional[int]):
        """
        验证信号创建参数
        
        Args:
            conn: 数据库连接
            scope_type: 范围类型
            scope_data: 范围数据
            ts_code: 标的代码（兼容性）
            category_id: 类别ID（兼容性）
            
        Raises:
            ValueError: 当参数验证失败时
        """
        # 兼容性处理：如果使用旧参数，则转换为新格式
        if ts_code and not scope_data:
            scope_type = "INSTRUMENT"
            scope_data = [ts_code]
        elif category_id and not scope_data:
            scope_type = "CATEGORY"
            scope_data = [str(category_id)]
        
        # 验证范围类型和数据
        if scope_type == "ALL_INSTRUMENTS":
            # ALL_INSTRUMENTS类型不存储具体scope_data，动态获取
            scope_data = None
            
        elif scope_type == "ALL_CATEGORIES":
            # ALL_CATEGORIES类型不存储具体scope_data，动态获取
            scope_data = None
            
        elif scope_type in ["MULTI_INSTRUMENT", "INSTRUMENT"]:
            if not scope_data:
                raise ValueError(f"{scope_type} scope_type 需要提供 scope_data")
            # 验证所有标的代码存在
            invalid_codes = signal_repo.validate_instrument_codes(conn, scope_data)
            if invalid_codes:
                raise ValueError(f"标的代码 {','.join(invalid_codes)} 不存在")
                
        elif scope_type in ["MULTI_CATEGORY", "CATEGORY"]:
            if not scope_data:
                raise ValueError(f"{scope_type} scope_type 需要提供 scope_data")
            # 验证所有类别ID存在  
            category_ids = [int(cat_id) for cat_id in scope_data]
            invalid_ids = signal_repo.validate_category_ids(conn, category_ids)
            if invalid_ids:
                raise ValueError(f"类别ID {','.join(map(str, invalid_ids))} 不存在")

    @staticmethod
    def get_signal_counts_by_date(trade_date: str) -> Dict[str, int]:
        """
        获取指定日期各类型信号的统计数量
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            
        Returns:
            各信号类型的数量字典
        """
        with get_conn() as conn:
            return signal_repo.get_signal_counts_by_date(conn, trade_date)


class SignalGenerationService:
    """信号生成业务服务"""

    @staticmethod
    def generate_stop_signals_for_position(ts_code: str, avg_cost: float, opening_date: str,
                                         stop_gain: float, stop_loss: float) -> Tuple[int, Optional[Tuple[str, str]]]:
        """
        为特定持仓生成止盈止损信号
        
        Args:
            ts_code: 标的代码
            avg_cost: 平均成本
            opening_date: 开仓日期
            stop_gain: 止盈比例
            stop_loss: 止损比例
            
        Returns:
            (信号数量, 日期范围) 或 (信号数量, None)
        """
        with get_conn() as conn:
            # 获取从开仓日期到今天的历史价格数据
            price_data = conn.execute("""
                SELECT trade_date, close 
                FROM price_eod 
                WHERE ts_code = ? AND trade_date >= ? 
                ORDER BY trade_date ASC
            """, (ts_code, opening_date)).fetchall()
            
            if not price_data:
                return 0, None
            
            signal_count = 0
            first_signal_date = None
            last_signal_date = None
            
            # 检查每个历史日期是否首次达到条件
            for trade_date, close_price in price_data:
                if not close_price:
                    continue
                
                # 计算收益率
                ret = (close_price - avg_cost) / avg_cost
                
                # 检查止盈条件
                if ret >= stop_gain:
                    signal_id = signal_repo.insert_signal_if_not_exists(
                        conn, trade_date, ts_code, "HIGH", "STOP_GAIN",
                        f"{ts_code} 收益率 {ret:.2%} 达到止盈目标 {stop_gain:.0%}"
                    )
                    if signal_id:
                        signal_count += 1
                        if first_signal_date is None:
                            first_signal_date = trade_date
                        last_signal_date = trade_date
                    # 找到首次触发就停止检查后续日期的止盈
                    break
                    
                # 检查止损条件
                elif ret <= -stop_loss:
                    signal_id = signal_repo.insert_signal_if_not_exists(
                        conn, trade_date, ts_code, "HIGH", "STOP_LOSS",
                        f"{ts_code} 收益率 {ret:.2%} 触发止损阈值 -{stop_loss:.0%}"
                    )
                    if signal_id:
                        signal_count += 1
                        if first_signal_date is None:
                            first_signal_date = trade_date
                        last_signal_date = trade_date
                    # 找到首次触发就停止检查后续日期的止损
                    break
            
            conn.commit()
            
            if first_signal_date and last_signal_date:
                return signal_count, (first_signal_date, last_signal_date)
            return signal_count, None

    @staticmethod
    def rebuild_all_historical_signals() -> Dict[str, Any]:
        """
        重建所有历史信号
        
        Returns:
            重建结果统计
        """
        with get_conn() as conn:
            # 清除现有的止盈止损信号
            signal_repo.delete_signals_by_type(conn, ['STOP_GAIN', 'STOP_LOSS'])
            conn.commit()
            
            # 获取配置参数
            from . import config_svc
            config = config_svc.get_config()
            stop_gain = config.get('stop_gain_pct', 20) / 100  # 转换为小数
            stop_loss = config.get('stop_loss_pct', 10) / 100  # 转换为小数
            
            # 获取所有当前持仓
            positions = conn.execute("""
                SELECT ts_code, avg_cost, opening_date 
                FROM position 
                WHERE shares > 0 AND avg_cost > 0 AND ts_code IS NOT NULL
            """).fetchall()
            
            signal_count = 0
            all_date_ranges = []
            
            for ts_code, avg_cost, opening_date in positions:
                if not opening_date or avg_cost <= 0:
                    continue
                
                count, date_range = SignalGenerationService.generate_stop_signals_for_position(
                    ts_code, float(avg_cost), opening_date, stop_gain, stop_loss
                )
                signal_count += count
                if date_range:
                    all_date_ranges.append(date_range)
            
            # 计算整体日期范围
            if all_date_ranges:
                min_date = min(dr[0] for dr in all_date_ranges)
                max_date = max(dr[1] for dr in all_date_ranges)
                date_range = f"{min_date} ~ {max_date}"
            else:
                date_range = "无信号生成"
            
            return {"count": signal_count, "date_range": date_range}

    @staticmethod
    def generate_current_signals(positions_df, stop_gain: float, stop_loss: float):
        """
        为当前持仓生成信号（用于日常计算）
        
        Args:
            positions_df: 持仓数据DataFrame
            stop_gain: 止盈比例
            stop_loss: 止损比例
        """
        with get_conn() as conn:
            for _, position in positions_df.iterrows():
                if position["cost"] <= 0 or not position["ts_code"]:
                    continue
                
                ts_code = position["ts_code"]
                avg_cost = float(position["avg_cost"])
                current_price = position.get("close")
                
                if not current_price:
                    continue
                
                # 计算收益率
                ret = (current_price - avg_cost) / avg_cost
                
                # 获取当前交易日期
                from datetime import datetime
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                # 检查止盈条件
                if ret >= stop_gain:
                    signal_repo.insert_signal_if_not_exists(
                        conn, current_date, ts_code, "HIGH", "STOP_GAIN",
                        f"{ts_code} 收益率 {ret:.2%} 达到止盈目标 {stop_gain:.0%}"
                    )
                    
                # 检查止损条件
                elif ret <= -stop_loss:
                    signal_repo.insert_signal_if_not_exists(
                        conn, current_date, ts_code, "HIGH", "STOP_LOSS",
                        f"{ts_code} 收益率 {ret:.2%} 触发止损阈值 -{stop_loss:.0%}"
                    )
            
            conn.commit()


# 向后兼容的函数别名
def list_signal(date_yyyymmdd: str, typ: Optional[str] = None, ts_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """向后兼容的信号列表函数"""
    return SignalService.get_signals_by_date(date_yyyymmdd, typ, ts_code)


def list_signal_all(typ: Optional[str] = None, ts_code: Optional[str] = None,
                   start_date: Optional[str] = None, end_date: Optional[str] = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
    """向后兼容的历史信号列表函数"""
    return SignalService.get_signals_history(typ, ts_code, start_date, end_date, limit)


def create_manual_signal_extended(trade_date: str, ts_code: Optional[str], category_id: Optional[int], 
                                 scope_type: str, scope_data: Optional[List[str]], level: str, 
                                 type: str, message: str) -> int:
    """向后兼容的扩展信号创建函数"""
    return SignalService.create_manual_signal(
        trade_date, ts_code, category_id, scope_type, scope_data, level, type, message
    )


def rebuild_all_historical_signals() -> Dict[str, Any]:
    """向后兼容的历史信号重建函数"""
    return SignalGenerationService.rebuild_all_historical_signals()
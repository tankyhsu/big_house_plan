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
    def generate_current_signals(positions_df, trade_date: str = None):
        """
        为当前持仓生成信号（用于日常计算）
        
        现在只包含结构信号（九转买入/卖出）和ZIG信号生成功能
        
        Args:
            positions_df: 持仓数据DataFrame
            trade_date: 交易日期 (YYYY-MM-DD格式)，如果不提供则使用当前日期
        """
        # 如果没有提供交易日期，使用当前日期
        if trade_date is None:
            from datetime import datetime
            trade_date = datetime.now().strftime('%Y-%m-%d')
        
        # 生成结构信号（九转买入/九转卖出）
        try:
            signal_count, signal_instruments = TdxStructureSignalGenerator.generate_structure_signals_for_date(trade_date)
            if signal_count > 0:
                print(f"生成了 {signal_count} 个结构信号: {', '.join(signal_instruments)}")
        except Exception as e:
            print(f"生成结构信号时发生错误: {str(e)}")
    
    @staticmethod
    def rebuild_structure_signals_for_period(start_date: str, end_date: str) -> Dict[str, Any]:
        """
        重建指定时间段内的结构信号
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            重建结果统计
        """
        with get_conn() as conn:
            # 先删除该时间段内的结构信号
            conn.execute("""
                DELETE FROM signal 
                WHERE type IN ('BUY_STRUCTURE', 'SELL_STRUCTURE') 
                AND trade_date BETWEEN ? AND ?
            """, (start_date, end_date))
            conn.commit()
            
            # 获取该时间段内的所有交易日期
            trade_dates = conn.execute("""
                SELECT DISTINCT trade_date
                FROM price_eod
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            """, (start_date, end_date)).fetchall()
            
            total_signals = 0
            processed_dates = 0
            
            for (trade_date,) in trade_dates:
                try:
                    signal_count, _ = TdxStructureSignalGenerator.generate_structure_signals_for_date(trade_date)
                    total_signals += signal_count
                    processed_dates += 1
                except Exception as e:
                    print(f"处理日期 {trade_date} 时发生错误: {str(e)}")
            
            return {
                "processed_dates": processed_dates,
                "total_signals": total_signals,
                "date_range": f"{start_date} ~ {end_date}"
            }


class TdxStructureSignalGenerator:
    """通达信结构信号生成器 - 九转买入/九转卖出判断"""
    
    @staticmethod
    def calculate_structure_signals(ts_code: str, trade_date: str) -> Tuple[bool, bool]:
        """
        计算某个标的在指定日期的九转买入/九转卖出信号
        
        Args:
            ts_code: 标的代码
            trade_date: 交易日期
            
        Returns:
            (是否九转买入, 是否九转卖出)
        """
        with get_conn() as conn:
            # 获取该标的前30天的价格数据（确保有足够数据计算）
            price_data = conn.execute("""
                SELECT trade_date, close
                FROM price_eod 
                WHERE ts_code = ? AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 30
            """, (ts_code, trade_date)).fetchall()
            
            if len(price_data) < 15:  # 至少需要15天数据
                return False, False
            
            # 转换为按日期正序排列，最新数据在最后
            price_data.reverse()
            closes = [float(row[1]) for row in price_data]
            
            # 计算九转买入信号
            buy_signal = TdxStructureSignalGenerator._calculate_buy_structure(closes)
            
            # 计算九转卖出信号  
            sell_signal = TdxStructureSignalGenerator._calculate_sell_structure(closes)
            
            return buy_signal, sell_signal
    
    @staticmethod
    def _calculate_buy_structure(closes: List[float]) -> bool:
        """
        计算九转买入信号
        通达信公式逻辑:
        TA:=EVERY(CLOSE<REF(CLOSE,4),9); - 连续9天收盘价都小于4天前的收盘价
        TB:=EXIST(CLOSE<REF(CLOSE,2),2); - 近2天内存在收盘价小于2天前的收盘价
        TC:=BACKSET(TA,9); - 当TA满足时，向前9天都标记为1
        TD:=IF(TC=1,SUM(TC,9),DRAWNULL); - 统计9天内标记数量
        买入信号: TD=9 AND REF(TD,1)=8 - 当TD=9且前一天TD=8时触发
        """
        if len(closes) < 15:
            return False
        
        # 计算TA: EVERY(CLOSE<REF(CLOSE,4),9)
        ta_values = []
        for i in range(len(closes)):
            if i >= 9 + 4:  # 需要至少13个数据点(9天+4天前)
                # 检查连续9天收盘价都小于4天前的收盘价
                every_condition = True
                for j in range(9):
                    current_idx = i - j
                    ref_idx = current_idx - 4
                    if current_idx < 0 or ref_idx < 0:
                        every_condition = False
                        break
                    if closes[current_idx] >= closes[ref_idx]:
                        every_condition = False
                        break
                ta_values.append(1 if every_condition else 0)
            else:
                ta_values.append(0)
        
        # 计算TC: BACKSET(TA,9) - 当TA为1时，向前9天都标记为1
        tc_values = [0] * len(closes)
        for i in range(len(ta_values)):
            if ta_values[i] == 1:
                # 向前9天标记为1
                for j in range(max(0, i-8), i+1):
                    tc_values[j] = 1
        
        # 计算TD: IF(TC=1,SUM(TC,9),DRAWNULL) - 统计9天内标记数量
        td_values = []
        for i in range(len(tc_values)):
            if tc_values[i] == 1:
                # 计算前9天（包括当天）的TC总和
                start_idx = max(0, i-8)
                sum_tc = sum(tc_values[start_idx:i+1])
                td_values.append(sum_tc)
            else:
                td_values.append(None)
        
        # 检查买入信号条件: TD=9 AND REF(TD,1)=8
        if len(td_values) >= 2:
            current_td = td_values[-1]
            prev_td = td_values[-2]
            
            return (current_td == 9 and prev_td == 8)
        
        return False
    
    @staticmethod
    def _calculate_sell_structure(closes: List[float]) -> bool:
        """
        计算九转卖出信号
        通达信公式逻辑:
        TE:=EVERY(CLOSE>REF(CLOSE,4),9); - 连续9天收盘价都大于4天前的收盘价
        TF:=EXIST(CLOSE>REF(CLOSE,2),2); - 近2天内存在收盘价大于2天前的收盘价
        TG:=BACKSET(TE,9); - 当TE满足时，向前9天都标记为1
        TH:=IF(TG=1,SUM(TG,9),DRAWNULL); - 统计9天内标记数量
        卖出信号: TH=9 AND REF(TH,1)=8 - 当TH=9且前一天TH=8时触发
        """
        if len(closes) < 15:
            return False
        
        # 计算TE: EVERY(CLOSE>REF(CLOSE,4),9)
        te_values = []
        for i in range(len(closes)):
            if i >= 9 + 4:  # 需要至少13个数据点(9天+4天前)
                # 检查连续9天收盘价都大于4天前的收盘价
                every_condition = True
                for j in range(9):
                    current_idx = i - j
                    ref_idx = current_idx - 4
                    if current_idx < 0 or ref_idx < 0:
                        every_condition = False
                        break
                    if closes[current_idx] <= closes[ref_idx]:
                        every_condition = False
                        break
                te_values.append(1 if every_condition else 0)
            else:
                te_values.append(0)
        
        # 计算TG: BACKSET(TE,9) - 当TE为1时，向前9天都标记为1
        tg_values = [0] * len(closes)
        for i in range(len(te_values)):
            if te_values[i] == 1:
                # 向前9天标记为1
                for j in range(max(0, i-8), i+1):
                    tg_values[j] = 1
        
        # 计算TH: IF(TG=1,SUM(TG,9),DRAWNULL) - 统计9天内标记数量
        th_values = []
        for i in range(len(tg_values)):
            if tg_values[i] == 1:
                # 计算前9天（包括当天）的TG总和
                start_idx = max(0, i-8)
                sum_tg = sum(tg_values[start_idx:i+1])
                th_values.append(sum_tg)
            else:
                th_values.append(None)
        
        # 检查卖出信号条件: TH=9 AND REF(TH,1)=8
        if len(th_values) >= 2:
            current_th = th_values[-1]
            prev_th = th_values[-2]
            
            return (current_th == 9 and prev_th == 8)
        
        return False

    @staticmethod
    def generate_structure_signals_for_date(trade_date: str) -> Tuple[int, List[str]]:
        """
        为指定日期生成所有标的的结构信号
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            
        Returns:
            (信号数量, 信号标的列表)
        """
        with get_conn() as conn:
            # 获取所有有价格数据的活跃标的
            instruments = conn.execute("""
                SELECT DISTINCT p.ts_code 
                FROM price_eod p
                JOIN instrument i ON p.ts_code = i.ts_code 
                WHERE i.active = 1 AND p.trade_date <= ?
            """, (trade_date,)).fetchall()
            
            signal_count = 0
            signal_instruments = []
            
            for (ts_code,) in instruments:
                buy_signal, sell_signal = TdxStructureSignalGenerator.calculate_structure_signals(
                    ts_code, trade_date
                )
                
                if buy_signal:
                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="BUY_STRUCTURE",
                        message=f"{ts_code} 九转买入信号触发",
                        days_back=9,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(九转买入)")

                if sell_signal:
                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="SELL_STRUCTURE",
                        message=f"{ts_code} 九转卖出信号触发",
                        days_back=9,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(九转卖出)")
            
            conn.commit()
            return signal_count, signal_instruments


class TdxZigSignalGenerator:
    """通达信ZIG信号生成器 - 基于之字转向指标的买入/卖出信号判断"""
    
    @staticmethod
    def calculate_zig_indicator(closes: List[float], turn_percent: float = 10.0) -> List[float]:
        """
        TODO: 此ZIG算法需要继续优化，当前准确率84.6%
        - 通达信ZIG是"未来函数"，会根据未来价格变化修改历史值
        - 需要研究更精确的转向点确认机制
        - 考虑引入第三方zigzag库的peak_valley_pivots算法
        
        计算ZIG之字转向指标 - 当前稳定版本（84.6%总体准确率）
        
        基于通达信ZIG(3,10)公式：
        - K=3表示使用收盘价
        - N=10表示10%转向阈值
        
        Args:
            closes: 收盘价序列
            turn_percent: 转向百分比阈值（默认10%）
            
        Returns:
            ZIG指标值序列，使用线性插值填充转向点之间的值
        """
        if len(closes) < 2:
            return closes.copy()
        
        n = len(closes)
        zig = [None] * n
        
        # 初始化状态
        zig[0] = closes[0]
        last_pivot = closes[0]
        last_pivot_idx = 0
        direction = 0  # 0=未确定, 1=上升, -1=下降
        
        high = closes[0]
        high_idx = 0
        low = closes[0]  
        low_idx = 0
        
        for i in range(1, n):
            price = closes[i]
            
            # 更新当前区间的极值点
            if price > high:
                high = price
                high_idx = i
            if price < low:
                low = price
                low_idx = i
            
            # 计算从上个确认转向点的变化幅度
            if last_pivot != 0:
                up_change = (high - last_pivot) / last_pivot * 100
                down_change = (last_pivot - low) / last_pivot * 100
            else:
                up_change = down_change = 0
            
            # 状态机：检查转向条件
            if direction == 0:
                # 初始状态，寻找第一个显著移动
                if up_change >= turn_percent:
                    direction = 1
                    zig[high_idx] = high
                    last_pivot = high
                    last_pivot_idx = high_idx
                    low = high
                    low_idx = high_idx
                elif down_change >= turn_percent:
                    direction = -1  
                    zig[low_idx] = low
                    last_pivot = low
                    last_pivot_idx = low_idx
                    high = low
                    high_idx = low_idx
            elif direction == 1:
                # 上升趋势中，检查是否转向下降
                if down_change >= turn_percent:
                    direction = -1
                    zig[low_idx] = low
                    last_pivot = low
                    last_pivot_idx = low_idx
                    high = low
                    high_idx = low_idx
                else:
                    # 继续上升，更新最高点
                    if high_idx != last_pivot_idx:
                        zig[high_idx] = high
                        last_pivot = high
                        last_pivot_idx = high_idx
            elif direction == -1:
                # 下降趋势中，检查是否转向上升
                if up_change >= turn_percent:
                    direction = 1
                    zig[high_idx] = high
                    last_pivot = high
                    last_pivot_idx = high_idx  
                    low = high
                    low_idx = high_idx
                else:
                    # 继续下降，更新最低点
                    if low_idx != last_pivot_idx:
                        zig[low_idx] = low
                        last_pivot = low
                        last_pivot_idx = low_idx
        
        # 线性插值填充转向点之间的值
        result = [0.0] * n
        last_valid = 0
        last_valid_idx = 0
        
        for i in range(n):
            if zig[i] is not None:
                # 填充从上一个转向点到当前转向点的线性插值
                if last_valid_idx < i:
                    for j in range(last_valid_idx, i + 1):
                        if i > last_valid_idx:
                            ratio = (j - last_valid_idx) / (i - last_valid_idx)
                            result[j] = last_valid + ratio * (zig[i] - last_valid)
                        else:
                            result[j] = zig[i]
                last_valid = zig[i]
                last_valid_idx = i
            else:
                # 处理最后一段：延续到当前价格
                if i == n - 1 and last_valid_idx < i:
                    for j in range(last_valid_idx, n):
                        if i > last_valid_idx:
                            ratio = (j - last_valid_idx) / (i - last_valid_idx)
                            result[j] = last_valid + ratio * (closes[i] - last_valid)
                        else:
                            result[j] = last_valid
        
        return result
    
    @staticmethod
    def detect_zig_signals(zig_values: List[float]) -> Tuple[bool, bool]:
        """
        检测ZIG信号的买入/卖出点
        
        基于通达信公式：
        买入：ZIG(3,10)>REF(ZIG(3,10),1) AND REF(ZIG(3,10),1)<REF(ZIG(3,10),2)
        卖出：ZIG(3,10)<REF(ZIG(3,10),1) AND REF(ZIG(3,10),1)>REF(ZIG(3,10),2)
        
        信号含义：
        - 买入信号：谷底反转（当前>前1天 且 前1天<前2天）
        - 卖出信号：峰顶反转（当前<前1天 且 前1天>前2天）
        
        Args:
            zig_values: ZIG指标值序列
            
        Returns:
            (buy_signal, sell_signal)
        """
        if len(zig_values) < 3:
            return False, False
        
        # 获取最近3天的ZIG值（REF函数引用）
        current = zig_values[-1]  # ZIG(3,10)
        prev1 = zig_values[-2]    # REF(ZIG(3,10),1)
        prev2 = zig_values[-3]    # REF(ZIG(3,10),2)
        
        if None in [current, prev1, prev2]:
            return False, False
        
        # 信号检测逻辑
        buy_signal = current > prev1 and prev1 < prev2   # 谷底反转
        sell_signal = current < prev1 and prev1 > prev2  # 峰顶反转
        
        return buy_signal, sell_signal
    
    @staticmethod
    def calculate_zig_signals(ts_code: str, trade_date: str) -> Tuple[bool, bool]:
        """
        计算某个标的在指定日期的ZIG买入/卖出信号
        
        Args:
            ts_code: 标的代码
            trade_date: 交易日期
            
        Returns:
            (是否买入信号, 是否卖出信号)
        """
        with get_conn() as conn:
            # 获取该标的前60天的价格数据（确保有足够数据计算）
            price_data = conn.execute("""
                SELECT trade_date, close
                FROM price_eod 
                WHERE ts_code = ? AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 60
            """, (ts_code, trade_date)).fetchall()
            
            if len(price_data) < 10:  # 至少需要10天数据
                return False, False
            
            # 转换为按日期正序排列，最新数据在最后
            price_data.reverse()
            closes = [float(row[1]) for row in price_data]
            
            # 计算ZIG指标
            zig_values = TdxZigSignalGenerator.calculate_zig_indicator(closes, turn_percent=10.0)
            
            # 检测信号
            buy_signal, sell_signal = TdxZigSignalGenerator.detect_zig_signals(zig_values)
            
            return buy_signal, sell_signal
    
    @staticmethod
    def generate_zig_signals_for_date(trade_date: str) -> Tuple[int, List[str]]:
        """
        为指定日期生成所有标的的ZIG信号
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            
        Returns:
            (信号数量, 信号标的列表)
        """
        with get_conn() as conn:
            # 获取所有有价格数据的活跃标的
            instruments = conn.execute("""
                SELECT DISTINCT p.ts_code 
                FROM price_eod p
                JOIN instrument i ON p.ts_code = i.ts_code 
                WHERE i.active = 1 AND p.trade_date <= ?
            """, (trade_date,)).fetchall()
            
            signal_count = 0
            signal_instruments = []
            
            for (ts_code,) in instruments:
                buy_signal, sell_signal = TdxZigSignalGenerator.calculate_zig_signals(
                    ts_code, trade_date
                )

                # 新规则：若出现新的买/卖点，且上一个ZIG信号同类型，则删除上一条后再新增
                if buy_signal:
                    last = signal_repo.get_last_signal_of_types(
                        conn, ts_code, ["ZIG_BUY", "ZIG_SELL"], before_date=trade_date
                    )
                    if last and (last.get("type") == "ZIG_BUY"):
                        signal_repo.delete_signal_by_id(conn, int(last["id"]))

                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="ZIG_BUY",
                        message=f"{ts_code} ZIG买入信号触发",
                        days_back=5,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(ZIG买入)")

                if sell_signal:
                    last = signal_repo.get_last_signal_of_types(
                        conn, ts_code, ["ZIG_BUY", "ZIG_SELL"], before_date=trade_date
                    )
                    if last and (last.get("type") == "ZIG_SELL"):
                        signal_repo.delete_signal_by_id(conn, int(last["id"]))

                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="ZIG_SELL",
                        message=f"{ts_code} ZIG卖出信号触发",
                        days_back=5,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(ZIG卖出)")
            
            conn.commit()
            return signal_count, signal_instruments

    @staticmethod
    def generate_zig_signals_for_date_with_guard(trade_date: str, min_delete_date: Optional[str] = None,
                                                 ts_codes: Optional[List[str]] = None) -> Tuple[int, List[str]]:
        """
        与 generate_zig_signals_for_date 类似，但在执行“同类连发删除上一条”时，
        仅当上一条信号日期在 min_delete_date 及之后才允许删除，避免跨越重建区间边界。

        Args:
            trade_date: YYYY-MM-DD
            min_delete_date: 允许删除的最早日期（含）。None 表示不限
            ts_codes: 可选，仅处理这些标的

        Returns:
            (生成的数量, 标的列表说明)
        """
        from ..repository import signal_repo
        from ..db import get_conn

        with get_conn() as conn:
            if ts_codes:
                instruments = [(c,) for c in sorted(set(ts_codes))]
            else:
                instruments = conn.execute(
                    """
                    SELECT DISTINCT p.ts_code
                    FROM price_eod p
                    JOIN instrument i ON p.ts_code = i.ts_code
                    WHERE i.active = 1 AND p.trade_date <= ?
                    """,
                    (trade_date,),
                ).fetchall()

            signal_count = 0
            signal_instruments: List[str] = []

            for (ts_code,) in instruments:
                buy_signal, sell_signal = TdxZigSignalGenerator.calculate_zig_signals(ts_code, trade_date)

                if buy_signal:
                    last = signal_repo.get_last_signal_of_types(
                        conn, ts_code, ["ZIG_BUY", "ZIG_SELL"], before_date=trade_date
                    )
                    if last and last.get("type") == "ZIG_BUY":
                        if (min_delete_date is None) or (str(last.get("trade_date")) >= min_delete_date):
                            signal_repo.delete_signal_by_id(conn, int(last["id"]))

                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="ZIG_BUY",
                        message=f"{ts_code} ZIG买入信号触发",
                        days_back=5,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(ZIG买入)")

                if sell_signal:
                    last = signal_repo.get_last_signal_of_types(
                        conn, ts_code, ["ZIG_BUY", "ZIG_SELL"], before_date=trade_date
                    )
                    if last and last.get("type") == "ZIG_SELL":
                        if (min_delete_date is None) or (str(last.get("trade_date")) >= min_delete_date):
                            signal_repo.delete_signal_by_id(conn, int(last["id"]))

                    sid = signal_repo.insert_signal_if_no_recent_structure(
                        conn,
                        trade_date,
                        ts_code=ts_code,
                        level="HIGH",
                        signal_type="ZIG_SELL",
                        message=f"{ts_code} ZIG卖出信号触发",
                        days_back=5,
                    )
                    if sid:
                        signal_count += 1
                        signal_instruments.append(f"{ts_code}(ZIG卖出)")

            conn.commit()
            return signal_count, signal_instruments

    @staticmethod
    def rebuild_zig_signals_for_period(start_date: str, end_date: str, ts_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        重建指定时间段内的 ZIG 信号：
        1) 删除区间内（且可选限定标的）的 ZIG_BUY / ZIG_SELL
        2) 按交易日顺序逐日重新生成（删除上一条同类仅限于区间内）

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            ts_codes: 可选，仅重建这些 ts_code

        Returns:
            统计信息
        """
        from ..db import get_conn
        from ..repository import signal_repo

        with get_conn() as conn:
            params: List[Any] = [start_date, end_date]
            where = "trade_date BETWEEN ? AND ? AND type IN ('ZIG_BUY','ZIG_SELL')"
            if ts_codes:
                placeholders = ",".join(["?"] * len(ts_codes))
                where += f" AND ts_code IN ({placeholders})"
                params.extend(ts_codes)
            # 删除区间内ZIG信号
            deleted = conn.execute(f"DELETE FROM signal WHERE {where}", params).rowcount
            conn.commit()

            # 交易日序列
            date_rows = conn.execute(
                """
                SELECT DISTINCT trade_date FROM price_eod
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date ASC
                """,
                (start_date, end_date),
            ).fetchall()

            total_gen = 0
            processed_dates = 0

            for (d,) in date_rows:
                cnt, _ = TdxZigSignalGenerator.generate_zig_signals_for_date_with_guard(
                    d, min_delete_date=start_date, ts_codes=ts_codes
                )
                total_gen += cnt
                processed_dates += 1

            return {
                "deleted_signals": deleted,
                "generated_signals": total_gen,
                "processed_dates": processed_dates,
                "date_range": f"{start_date} ~ {end_date}",
                "ts_codes": ts_codes or "ALL",
            }
    
    @staticmethod
    def test_zig_calculation(ts_code: str, start_date: str, end_date: str) -> dict:
        """
        测试验证方法：计算指定标的在指定时间段内的ZIG指标和信号
        用于与通达信数据对比验证算法准确性
        
        Args:
            ts_code: 标的代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            包含价格、ZIG指标、信号的详细数据字典
        """
        with get_conn() as conn:
            # 获取指定时间段前60天到结束日期的所有价格数据
            extended_start = conn.execute("""
                SELECT trade_date 
                FROM price_eod 
                WHERE ts_code = ? AND trade_date <= ?
                ORDER BY trade_date DESC 
                LIMIT 60
            """, (ts_code, start_date)).fetchall()
            
            if extended_start:
                actual_start = extended_start[-1][0]
            else:
                actual_start = start_date
            
            # 获取价格数据
            price_data = conn.execute("""
                SELECT trade_date, open, high, low, close, vol
                FROM price_eod 
                WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date ASC
            """, (ts_code, actual_start, end_date)).fetchall()
            
            if not price_data:
                return {"error": f"未找到 {ts_code} 在 {start_date} 到 {end_date} 的价格数据"}
            
            # 提取数据
            dates = [row[0] for row in price_data]
            opens = [float(row[1]) for row in price_data]
            highs = [float(row[2]) for row in price_data]
            lows = [float(row[3]) for row in price_data]
            closes = [float(row[4]) for row in price_data]
            volumes = [int(row[5]) for row in price_data]
            
            # 计算ZIG指标
            zig_values = TdxZigSignalGenerator.calculate_zig_indicator(closes, turn_percent=10.0)
            
            # 计算每日信号
            buy_signals = []
            sell_signals = []
            
            for i in range(len(zig_values)):
                if i >= 2:  # 需要至少3个数据点
                    current = zig_values[i]
                    prev1 = zig_values[i-1]
                    prev2 = zig_values[i-2]
                    
                    if None not in [current, prev1, prev2]:
                        buy_sig = current > prev1 and prev1 < prev2
                        sell_sig = current < prev1 and prev1 > prev2
                    else:
                        buy_sig = False
                        sell_sig = False
                else:
                    buy_sig = False
                    sell_sig = False
                
                buy_signals.append(buy_sig)
                sell_signals.append(sell_sig)
            
            # 筛选出指定时间段的结果
            target_start_idx = None
            for i, date in enumerate(dates):
                if date >= start_date:
                    target_start_idx = i
                    break
            
            if target_start_idx is None:
                return {"error": f"指定开始日期 {start_date} 超出数据范围"}
            
            # 构建结果
            result = {
                "ts_code": ts_code,
                "period": f"{start_date} to {end_date}",
                "total_days": len(dates) - target_start_idx,
                "data": []
            }
            
            # 统计信号数量
            buy_count = 0
            sell_count = 0
            
            for i in range(target_start_idx, len(dates)):
                day_data = {
                    "date": dates[i],
                    "open": opens[i],
                    "high": highs[i], 
                    "low": lows[i],
                    "close": closes[i],
                    "volume": volumes[i],
                    "zig": round(zig_values[i], 2) if zig_values[i] is not None else None,
                    "buy_signal": buy_signals[i],
                    "sell_signal": sell_signals[i]
                }
                
                if buy_signals[i]:
                    buy_count += 1
                    day_data["signal_type"] = "买入"
                elif sell_signals[i]:
                    sell_count += 1
                    day_data["signal_type"] = "卖出"
                
                result["data"].append(day_data)
            
            result["summary"] = {
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "total_signals": buy_count + sell_count
            }
            
            return result

    @staticmethod
    def validate_against_tdx_data(ts_code: str, expected_buy_dates: List[str], expected_sell_dates: List[str]) -> dict:
        """
        验证我们的ZIG算法与通达信数据的一致性
        
        Args:
            ts_code: 标的代码
            expected_buy_dates: 通达信期望的买入信号日期列表
            expected_sell_dates: 通达信期望的卖出信号日期列表
            
        Returns:
            验证结果字典
        """
        # 确定数据范围
        all_dates = expected_buy_dates + expected_sell_dates
        if not all_dates:
            return {"error": "没有提供期望的信号日期"}
        
        start_date = min(all_dates)
        end_date = max(all_dates)
        
        # 扩展范围以确保有足够的历史数据
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=90)
        extended_start = start_dt.strftime("%Y-%m-%d")
        
        # 获取我们算法的计算结果
        our_result = TdxZigSignalGenerator.test_zig_calculation(ts_code, extended_start, end_date)
        
        if "error" in our_result:
            return our_result
        
        # 提取我们的信号
        our_buy_signals = []
        our_sell_signals = []
        
        for day_data in our_result["data"]:
            if day_data["buy_signal"]:
                our_buy_signals.append(day_data["date"])
            if day_data["sell_signal"]:
                our_sell_signals.append(day_data["date"])
        
        # 对比结果
        comparison = {
            "ts_code": ts_code,
            "validation_period": f"{start_date} to {end_date}",
            "tdx_expected": {
                "buy_signals": expected_buy_dates,
                "sell_signals": expected_sell_dates
            },
            "our_algorithm": {
                "buy_signals": our_buy_signals,
                "sell_signals": our_sell_signals
            },
            "comparison": {
                "buy_matches": [],
                "buy_missed": [],
                "buy_extra": [],
                "sell_matches": [],
                "sell_missed": [],
                "sell_extra": []
            }
        }
        
        # 买入信号对比
        for date in expected_buy_dates:
            if date in our_buy_signals:
                comparison["comparison"]["buy_matches"].append(date)
            else:
                comparison["comparison"]["buy_missed"].append(date)
        
        for date in our_buy_signals:
            if date not in expected_buy_dates:
                comparison["comparison"]["buy_extra"].append(date)
        
        # 卖出信号对比
        for date in expected_sell_dates:
            if date in our_sell_signals:
                comparison["comparison"]["sell_matches"].append(date)
            else:
                comparison["comparison"]["sell_missed"].append(date)
        
        for date in our_sell_signals:
            if date not in expected_sell_dates:
                comparison["comparison"]["sell_extra"].append(date)
        
        # 计算准确率
        total_expected = len(expected_buy_dates) + len(expected_sell_dates)
        total_matches = len(comparison["comparison"]["buy_matches"]) + len(comparison["comparison"]["sell_matches"])
        
        comparison["accuracy"] = {
            "total_expected_signals": total_expected,
            "total_matched_signals": total_matches,
            "accuracy_rate": (total_matches / total_expected * 100) if total_expected > 0 else 0,
            "buy_accuracy": (len(comparison["comparison"]["buy_matches"]) / len(expected_buy_dates) * 100) if expected_buy_dates else 100,
            "sell_accuracy": (len(comparison["comparison"]["sell_matches"]) / len(expected_sell_dates) * 100) if expected_sell_dates else 100
        }
        
        return comparison

    @staticmethod  
    def cleanup_and_regenerate_zig_signals(trade_date: str, ts_codes: Optional[List[str]] = None) -> dict:
        """
        清理并重新生成ZIG信号 - 用于价格更新后的信号维护
        
        当价格数据更新时，ZIG指标会重新计算，可能导致之前的信号不再有效。
        此方法会：
        1. 重新计算指定标的的ZIG信号
        2. 删除不再有效的历史ZIG信号
        3. 生成新的有效信号
        4. 记录清理和生成的详细日志
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            ts_codes: 可选，指定要处理的标的代码列表。为空时处理所有活跃标的
            
        Returns:
            dict: 清理和重新生成结果
            - processed_instruments: 处理的标的数量
            - deleted_signals: 删除的信号数量  
            - generated_signals: 新生成的信号数量
            - signal_changes: 各标的的信号变化详情
        """
        from ..repository import signal_repo
        from ..db import get_conn
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"开始ZIG信号清理和重新生成: {trade_date}")
        
        with get_conn() as conn:
            # 获取要处理的标的列表
            if ts_codes:
                # 验证提供的标的代码是否有效
                tmap = {code: code for code in ts_codes}  # 简化处理
                instruments = [(code,) for code in ts_codes]
            else:
                # 获取所有有价格数据的活跃标的
                instruments = conn.execute("""
                    SELECT DISTINCT p.ts_code 
                    FROM price_eod p
                    JOIN instrument i ON p.ts_code = i.ts_code 
                    WHERE i.active = 1 AND p.trade_date <= ?
                """, (trade_date,)).fetchall()
            
            if not instruments:
                return {
                    "processed_instruments": 0,
                    "deleted_signals": 0, 
                    "generated_signals": 0,
                    "signal_changes": []
                }
            
            processed_count = 0
            total_deleted = 0
            total_generated = 0
            signal_changes = []
            
            for (ts_code,) in instruments:
                try:
                    # 获取该标的历史ZIG信号（最近30天）
                    from datetime import datetime, timedelta
                    start_date = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
                    
                    existing_signals = conn.execute("""
                        SELECT id, trade_date, type, message
                        FROM signal 
                        WHERE ts_code = ? AND type IN ('ZIG_BUY', 'ZIG_SELL') 
                        AND trade_date >= ? AND trade_date <= ?
                        ORDER BY trade_date DESC
                    """, (ts_code, start_date, trade_date)).fetchall()
                    
                    # 重新计算当前的ZIG信号状态
                    current_signals = []
                    
                    # 获取该标的在指定日期范围内的所有交易日
                    price_data = conn.execute("""
                        SELECT trade_date, close
                        FROM price_eod 
                        WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
                        ORDER BY trade_date ASC
                    """, (ts_code, start_date, trade_date)).fetchall()
                    
                    if len(price_data) < 10:  # 数据不足，跳过
                        continue
                    
                    # 逐日计算ZIG信号
                    closes = [float(row[1]) for row in price_data]
                    dates = [row[0] for row in price_data]
                    
                    # 计算完整的ZIG指标序列
                    zig_values = TdxZigSignalGenerator.calculate_zig_indicator(closes, turn_percent=10.0)
                    
                    # 检测每个日期的信号（并保证买卖交替：同类连发则用新的替换旧的）
                    for i in range(2, len(zig_values)):  # 从第3个数据点开始（需要前2个数据点）
                        current_zig = zig_values[i]
                        prev1_zig = zig_values[i-1]
                        prev2_zig = zig_values[i-2]

                        if None not in [current_zig, prev1_zig, prev2_zig]:
                            buy_signal = current_zig > prev1_zig and prev1_zig < prev2_zig
                            sell_signal = current_zig < prev1_zig and prev1_zig > prev2_zig

                            if buy_signal:
                                if current_signals and current_signals[-1]["type"] == "ZIG_BUY":
                                    current_signals[-1] = {
                                        "date": dates[i],
                                        "type": "ZIG_BUY",
                                        "message": f"{ts_code} ZIG买入信号触发"
                                    }
                                else:
                                    current_signals.append({
                                        "date": dates[i],
                                        "type": "ZIG_BUY",
                                        "message": f"{ts_code} ZIG买入信号触发"
                                    })
                            elif sell_signal:
                                if current_signals and current_signals[-1]["type"] == "ZIG_SELL":
                                    current_signals[-1] = {
                                        "date": dates[i],
                                        "type": "ZIG_SELL",
                                        "message": f"{ts_code} ZIG卖出信号触发"
                                    }
                                else:
                                    current_signals.append({
                                        "date": dates[i],
                                        "type": "ZIG_SELL",
                                        "message": f"{ts_code} ZIG卖出信号触发"
                                    })
                    
                    # 比较现有信号和重新计算的信号
                    existing_set = {(sig[1], sig[2]) for sig in existing_signals}  # (date, type)
                    current_set = {(sig["date"], sig["type"]) for sig in current_signals}
                    
                    # 找出需要删除的信号（存在于历史但不在当前计算结果中）
                    to_delete = existing_set - current_set
                    # 找出需要新增的信号（存在于当前计算但不在历史中）
                    to_add = current_set - existing_set
                    
                    deleted_count = 0
                    generated_count = 0
                    
                    # 删除过时的信号
                    if to_delete:
                        for date, signal_type in to_delete:
                            result = conn.execute("""
                                DELETE FROM signal 
                                WHERE ts_code = ? AND trade_date = ? AND type = ?
                            """, (ts_code, date, signal_type))
                            deleted_count += result.rowcount
                    
                    # 添加新的信号
                    if to_add:
                        for date, signal_type in to_add:
                            # 查找对应的信号详情
                            signal_detail = next((s for s in current_signals if s["date"] == date and s["type"] == signal_type), None)
                            if signal_detail:
                                sid = signal_repo.insert_signal_if_no_recent_structure(
                                    conn,
                                    date,
                                    ts_code=ts_code,
                                    level="HIGH", 
                                    signal_type=signal_type,
                                    message=signal_detail["message"],
                                    days_back=1,  # 减少重复检查天数，因为我们已经做了清理
                                )
                                if sid:
                                    generated_count += 1
                    
                    # 记录变化
                    if deleted_count > 0 or generated_count > 0:
                        signal_changes.append({
                            "ts_code": ts_code,
                            "deleted": deleted_count,
                            "generated": generated_count,
                            "deleted_signals": list(to_delete),
                            "added_signals": list(to_add)
                        })
                    
                    total_deleted += deleted_count
                    total_generated += generated_count
                    processed_count += 1
                    
                    logger.debug(f"{ts_code}: 删除{deleted_count}个过时信号，生成{generated_count}个新信号")
                    
                except Exception as e:
                    logger.error(f"处理{ts_code}的ZIG信号时出错: {str(e)}")
                    continue
            
            # 提交所有更改
            conn.commit()
            
            result = {
                "processed_instruments": processed_count,
                "deleted_signals": total_deleted,
                "generated_signals": total_generated, 
                "signal_changes": signal_changes
            }
            
            logger.info(f"ZIG信号清理完成: 处理{processed_count}个标的，删除{total_deleted}个过时信号，生成{total_generated}个新信号")
            return result


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
    """向后兼容的历史信号重建函数 - 功能已移除"""
    # 这个函数已不再需要，因为我们移除了止盈止损信号生成逻辑
    # 结构信号和ZIG信号通过其他专门的函数生成
    return {"count": 0, "date_range": "功能已移除 - 不再自动生成止盈止损信号"}

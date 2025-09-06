# ZIG算法备份 - 84.6%准确率版本
# 备份时间: 2025-09-06

class TdxZigSignalGeneratorBackup:
    """ZIG信号生成器备份版本 - 84.6%总体准确率"""
    
    @staticmethod
    def calculate_zig_indicator(closes: list[float], turn_percent: float = 10.0) -> list[float]:
        """
        计算ZIG之字转向指标 - 简化版经典算法
        
        Args:
            closes: 收盘价序列
            turn_percent: 转向百分比阈值（默认10%）
            
        Returns:
            ZIG指标值序列
        """
        if len(closes) < 2:
            return closes.copy()
        
        n = len(closes)
        zig = [None] * n
        
        # 初始化
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
            
            # 更新高低点
            if price > high:
                high = price
                high_idx = i
            if price < low:
                low = price
                low_idx = i
            
            # 计算变化幅度
            if last_pivot != 0:
                up_change = (high - last_pivot) / last_pivot * 100
                down_change = (last_pivot - low) / last_pivot * 100
            else:
                up_change = down_change = 0
            
            # 检查转向条件
            if direction == 0:
                # 初始状态，寻找第一个显著移动
                if up_change >= turn_percent:
                    direction = 1
                    zig[high_idx] = high
                    last_pivot = high
                    last_pivot_idx = high_idx
                    # 重置低点
                    low = high
                    low_idx = high_idx
                elif down_change >= turn_percent:
                    direction = -1  
                    zig[low_idx] = low
                    last_pivot = low
                    last_pivot_idx = low_idx
                    # 重置高点
                    high = low
                    high_idx = low_idx
            elif direction == 1:
                # 上升趋势中，检查是否转向下降
                if down_change >= turn_percent:
                    direction = -1
                    zig[low_idx] = low
                    last_pivot = low
                    last_pivot_idx = low_idx
                    # 重置高点
                    high = low
                    high_idx = low_idx
                else:
                    # 继续上升或创新高
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
                    # 重置低点
                    low = high
                    low_idx = high_idx
                else:
                    # 继续下降或创新低
                    if low_idx != last_pivot_idx:
                        zig[low_idx] = low
                        last_pivot = low
                        last_pivot_idx = low_idx
        
        # 填充中间值
        result = [0.0] * n
        last_valid = 0
        last_valid_idx = 0
        
        for i in range(n):
            if zig[i] is not None:
                # 填充从上一个有效点到当前点的线性插值
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
                # 如果是最后一段，延续到当前价格
                if i == n - 1 and last_valid_idx < i:
                    for j in range(last_valid_idx, n):
                        if i > last_valid_idx:
                            ratio = (j - last_valid_idx) / (i - last_valid_idx)
                            result[j] = last_valid + ratio * (closes[i] - last_valid)
                        else:
                            result[j] = last_valid
        
        return result

    @staticmethod
    def detect_zig_signals(zig_values: list[float]) -> tuple[bool, bool]:
        """
        检测ZIG信号的买入/卖出点
        买入：ZIG(3,10)>REF(ZIG(3,10),1)AND REF(ZIG(3,10),1)<REF(ZIG(3,10),2)
        卖出：ZIG(3,10)<REF(ZIG(3,10),1)AND REF(ZIG(3,10),1)>REF(ZIG(3,10),2)
        
        Args:
            zig_values: ZIG指标值序列
            
        Returns:
            (buy_signal, sell_signal)
        """
        if len(zig_values) < 3:
            return False, False
        
        # 获取最近3天的ZIG值
        current = zig_values[-1]  # ZIG(3,10)
        prev1 = zig_values[-2]    # REF(ZIG(3,10),1)
        prev2 = zig_values[-3]    # REF(ZIG(3,10),2)
        
        if None in [current, prev1, prev2]:
            return False, False
        
        # 买入信号：当前>前1天 AND 前1天<前2天（谷底反转）
        buy_signal = current > prev1 and prev1 < prev2
        
        # 卖出信号：当前<前1天 AND 前1天>前2天（峰顶反转）
        sell_signal = current < prev1 and prev1 > prev2
        
        return buy_signal, sell_signal

# 验证结果记录：
# 301606.SZ: 100% (4/4)
# 300573.SZ: 83.3% (5/6) - 漏掉 2025-06-05 卖出
# 002847.SZ: 66.7% (2/3) - 漏掉 2025-06-05 卖出
# 总体: 84.6% (11/13)
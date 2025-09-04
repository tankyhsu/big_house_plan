"""
持仓状态服务 - 实时计算止盈止损等状态信息
重构思路：将止盈止损从时间事件转为基于成本的客观计算
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from ..repository import reporting_repo
from ..db import get_conn
from . import config_svc


class PositionStatusService:
    """持仓状态计算服务"""
    
    @staticmethod
    def get_current_position_status(date_yyyymmdd: str = None, ts_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取当前持仓的实时状态（止盈/止损/正常）
        
        Args:
            date_yyyymmdd: 计算日期，默认为今天
            ts_code: 指定标的代码，为空则返回所有持仓
            
        Returns:
            持仓状态列表，每个包含：
            - ts_code: 标的代码
            - shares: 持股数量
            - avg_cost: 平均成本
            - current_price: 当前价格
            - return_rate: 收益率
            - status: 状态 ('STOP_GAIN', 'STOP_LOSS', 'NORMAL')
            - stop_gain_threshold: 止盈阈值
            - stop_loss_threshold: 止损阈值
            - message: 状态描述
        """
        if date_yyyymmdd is None:
            date_yyyymmdd = datetime.now().strftime("%Y%m%d")
        
        # 转换为破折号格式
        date_dash = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
        
        # 获取配置参数 - 配置中的值已经是小数形式 (0.3 = 30%, 0.12 = 12%)
        config = config_svc.get_config()
        stop_gain_pct = config.get('stop_gain_pct', 0.20)  # 已经是小数，不需要除以100
        stop_loss_pct = config.get('stop_loss_pct', 0.10)  # 已经是小数，不需要除以100
        
        with get_conn() as conn:
            # 获取持仓和价格数据
            position_data = reporting_repo.active_instruments_with_pos_and_price(conn, date_dash)
            
            results = []
            for row in position_data:
                shares = float(row["shares"] or 0)
                avg_cost = float(row["avg_cost"] or 0)
                current_price = row["eod_close"]
                ts_code_row = row["ts_code"]
                
                # 跳过无持仓或无效数据
                if shares <= 0 or avg_cost <= 0 or not ts_code_row:
                    continue
                    
                # 如果指定了ts_code，只返回匹配的
                if ts_code and ts_code_row != ts_code:
                    continue
                
                # 处理价格缺失情况（使用平均成本作为fallback）
                if current_price is None:
                    current_price = avg_cost
                    price_fallback_used = True
                else:
                    current_price = float(current_price)
                    price_fallback_used = False
                
                # 计算收益率
                return_rate = (current_price - avg_cost) / avg_cost
                
                # 判断状态
                status, message = PositionStatusService._determine_status(
                    ts_code_row, return_rate, stop_gain_pct, stop_loss_pct
                )
                
                results.append({
                    "ts_code": ts_code_row,
                    "category_id": row["category_id"],
                    "shares": shares,
                    "avg_cost": avg_cost,
                    "current_price": current_price,
                    "return_rate": return_rate,
                    "status": status,
                    "stop_gain_threshold": stop_gain_pct,
                    "stop_loss_threshold": stop_loss_pct,
                    "message": message,
                    "price_fallback_used": price_fallback_used
                })
            
            return results
    
    @staticmethod
    def _determine_status(ts_code: str, return_rate: float, stop_gain_pct: float, stop_loss_pct: float) -> tuple[str, str]:
        """
        根据收益率确定持仓状态
        
        Args:
            ts_code: 标的代码
            return_rate: 收益率（小数）
            stop_gain_pct: 止盈阈值（小数）
            stop_loss_pct: 止损阈值（小数）
            
        Returns:
            (status, message) 状态和描述信息
        """
        if return_rate >= stop_gain_pct:
            return "STOP_GAIN", f"{ts_code} 收益率 {return_rate:.2%} 达到止盈目标 {stop_gain_pct:.0%}"
        elif return_rate <= -stop_loss_pct:
            return "STOP_LOSS", f"{ts_code} 收益率 {return_rate:.2%} 触发止损阈值 -{stop_loss_pct:.0%}"
        else:
            return "NORMAL", f"{ts_code} 收益率 {return_rate:.2%} 正常范围内"
    
    @staticmethod
    def get_position_alerts_count(date_yyyymmdd: str = None) -> Dict[str, int]:
        """
        获取持仓状态统计（用于Dashboard显示）
        
        Args:
            date_yyyymmdd: 计算日期，默认为今天
            
        Returns:
            {"stop_gain": 止盈数量, "stop_loss": 止损数量, "normal": 正常数量}
        """
        position_status = PositionStatusService.get_current_position_status(date_yyyymmdd)
        
        counts = {"stop_gain": 0, "stop_loss": 0, "normal": 0}
        for pos in position_status:
            status = pos["status"]
            if status == "STOP_GAIN":
                counts["stop_gain"] += 1
            elif status == "STOP_LOSS":
                counts["stop_loss"] += 1
            else:
                counts["normal"] += 1
        
        return counts
    
    @staticmethod
    def get_position_status_by_instrument(ts_code: str, date_yyyymmdd: str = None) -> Optional[Dict[str, Any]]:
        """
        获取特定标的的持仓状态
        
        Args:
            ts_code: 标的代码
            date_yyyymmdd: 计算日期，默认为今天
            
        Returns:
            持仓状态信息，如果没有持仓则返回None
        """
        status_list = PositionStatusService.get_current_position_status(date_yyyymmdd, ts_code)
        return status_list[0] if status_list else None
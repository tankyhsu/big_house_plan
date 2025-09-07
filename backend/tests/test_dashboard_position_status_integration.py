"""
测试 Dashboard API 与 PositionStatusService 的集成
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from backend.services.dashboard_svc import get_dashboard


class TestDashboardPositionStatusIntegration(unittest.TestCase):

    @patch('backend.services.position_status_svc.PositionStatusService.get_position_alerts_count')
    @patch('backend.services.signal_svc.SignalService.get_signal_counts_by_date')
    @patch('backend.services.dashboard_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.dashboard_svc.get_conn')
    def test_get_dashboard_includes_position_status(self, mock_get_conn, mock_reporting_repo, 
                                                   mock_signal_counts, mock_position_alerts):
        """测试Dashboard API包含实时持仓状态信息"""
        # 设置mock返回值
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        # 模拟持仓和价格数据
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000001.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 10.0,
                'eod_close': 12.0
            }
        ]
        
        # 模拟历史信号统计（来自signal表的快照数据）
        mock_signal_counts.return_value = {
            'stop_gain': 1,
            'stop_loss': 0
        }
        
        # 模拟实时持仓状态统计
        mock_position_alerts.return_value = {
            'stop_gain': 2,
            'stop_loss': 1,
            'normal': 5
        }
        
        # 执行测试
        result = get_dashboard("20240101")
        
        # 验证返回结果包含所有必要字段
        self.assertIn("date", result)
        self.assertIn("kpi", result)
        self.assertIn("signals", result)
        self.assertIn("position_status", result)  # 新增字段
        self.assertIn("price_fallback_used", result)
        
        # 验证KPI计算
        expected_mv = 1000.0 * 12.0  # 12000
        expected_cost = 1000.0 * 10.0  # 10000
        expected_pnl = expected_mv - expected_cost  # 2000
        expected_ret = expected_pnl / expected_cost  # 0.2
        
        self.assertEqual(result["kpi"]["market_value"], expected_mv)
        self.assertEqual(result["kpi"]["cost"], expected_cost)
        self.assertEqual(result["kpi"]["unrealized_pnl"], expected_pnl)
        self.assertAlmostEqual(result["kpi"]["ret"], expected_ret, places=4)
        
        # 验证历史信号统计（来自signal表）
        self.assertEqual(result["signals"]["stop_gain"], 1)
        self.assertEqual(result["signals"]["stop_loss"], 0)
        
        # 验证实时持仓状态统计（新增功能）
        self.assertEqual(result["position_status"]["stop_gain"], 2)
        self.assertEqual(result["position_status"]["stop_loss"], 1)
        self.assertEqual(result["position_status"]["normal"], 5)
        
        # 验证调用了正确的方法
        mock_position_alerts.assert_called_once_with("20240101")
        mock_signal_counts.assert_called_once_with("2024-01-01")

    @patch('backend.services.position_status_svc.PositionStatusService.get_position_alerts_count')
    @patch('backend.services.signal_svc.SignalService.get_signal_counts_by_date')
    @patch('backend.services.dashboard_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.dashboard_svc.get_conn')
    def test_get_dashboard_backward_compatibility(self, mock_get_conn, mock_reporting_repo, 
                                                 mock_signal_counts, mock_position_alerts):
        """测试修改后的Dashboard API仍保持向后兼容"""
        # 设置mock返回值
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_reporting_repo.return_value = []
        mock_signal_counts.return_value = {'stop_gain': 0, 'stop_loss': 0}
        mock_position_alerts.return_value = {'stop_gain': 0, 'stop_loss': 0, 'normal': 0}
        
        result = get_dashboard("20240101")
        
        # 验证原有字段仍然存在且格式正确
        self.assertEqual(result["date"], "2024-01-01")
        self.assertIsInstance(result["kpi"], dict)
        self.assertIsInstance(result["signals"], dict)
        self.assertIsInstance(result["price_fallback_used"], bool)
        
        # 验证新字段已添加
        self.assertIsInstance(result["position_status"], dict)


if __name__ == '__main__':
    unittest.main()
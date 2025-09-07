"""
测试新的信号聚合API端点
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.api import app


class TestSignalsCurrentStatusAPI(unittest.TestCase):

    def setUp(self):
        """测试前准备"""
        self.client = TestClient(app)

    @patch('backend.services.position_status_svc.PositionStatusService.get_position_alerts_count')
    @patch('backend.services.signal_svc.SignalService.get_signal_counts_by_date')
    @patch('backend.services.position_status_svc.PositionStatusService.get_current_position_status')
    @patch('backend.services.signal_svc.SignalService.get_signals_by_date')
    def test_api_signals_current_status(self, mock_event_signals, mock_position_status, 
                                       mock_signal_counts, mock_position_counts):
        """测试信号状态聚合API"""
        # 设置mock返回值
        mock_event_signals.return_value = [
            {"id": 1, "ts_code": "000001.SZ", "type": "MANUAL_ALERT", "message": "手动提醒"}
        ]
        
        mock_position_status.return_value = [
            {
                "ts_code": "000002.SZ",
                "status": "STOP_GAIN", 
                "return_rate": 0.25,
                "message": "000002.SZ 收益率 25.00% 达到止盈目标 20%"
            }
        ]
        
        mock_signal_counts.return_value = {"stop_gain": 0, "stop_loss": 1}
        mock_position_counts.return_value = {"stop_gain": 2, "stop_loss": 0, "normal": 5}
        
        # 调用API
        response = self.client.get("/api/signals/current-status?date=20240101")
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证数据结构
        self.assertIn("date", data)
        self.assertIn("event_signals", data)
        self.assertIn("position_status", data)
        self.assertIn("summary", data)
        
        self.assertEqual(data["date"], "2024-01-01")
        
        # 验证事件信号
        self.assertEqual(len(data["event_signals"]), 1)
        self.assertEqual(data["event_signals"][0]["type"], "MANUAL_ALERT")
        
        # 验证持仓状态
        self.assertEqual(len(data["position_status"]), 1)
        self.assertEqual(data["position_status"][0]["status"], "STOP_GAIN")
        
        # 验证汇总信息
        summary = data["summary"]
        self.assertEqual(summary["event_counts"]["stop_gain"], 0)
        self.assertEqual(summary["event_counts"]["stop_loss"], 1)
        self.assertEqual(summary["position_counts"]["stop_gain"], 2)
        self.assertEqual(summary["position_counts"]["stop_loss"], 0)
        self.assertEqual(summary["position_counts"]["normal"], 5)
        
        # 验证调用了正确的方法
        mock_event_signals.assert_called_once_with("20240101")
        mock_position_status.assert_called_once_with("20240101")
        mock_signal_counts.assert_called_once_with("2024-01-01")
        mock_position_counts.assert_called_once_with("20240101")

    @patch('backend.services.position_status_svc.PositionStatusService.get_position_status_by_instrument')
    def test_api_positions_status_single(self, mock_get_position):
        """测试获取单个标的持仓状态"""
        # 设置mock返回值
        mock_get_position.return_value = {
            "ts_code": "000001.SZ",
            "status": "STOP_LOSS",
            "return_rate": -0.12,
            "message": "000001.SZ 收益率 -12.00% 触发止损阈值 -10%"
        }
        
        # 调用API
        response = self.client.get("/api/positions/status?date=20240101&ts_code=000001.SZ")
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["ts_code"], "000001.SZ")
        self.assertEqual(data["status"], "STOP_LOSS")
        self.assertAlmostEqual(data["return_rate"], -0.12, places=4)
        
        mock_get_position.assert_called_once_with("000001.SZ", "20240101")

    @patch('backend.services.position_status_svc.PositionStatusService.get_position_status_by_instrument')
    def test_api_positions_status_not_found(self, mock_get_position):
        """测试获取不存在标的的持仓状态"""
        # 设置mock返回值
        mock_get_position.return_value = None
        
        # 调用API
        response = self.client.get("/api/positions/status?date=20240101&ts_code=999999.SZ")
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("error", data)
        self.assertEqual(data["error"], "未找到该标的的持仓")

    @patch('backend.services.position_status_svc.PositionStatusService.get_current_position_status')
    def test_api_positions_status_all(self, mock_get_all_positions):
        """测试获取所有持仓状态"""
        # 设置mock返回值
        mock_get_all_positions.return_value = [
            {"ts_code": "000001.SZ", "status": "NORMAL", "return_rate": 0.05},
            {"ts_code": "000002.SZ", "status": "STOP_GAIN", "return_rate": 0.25}
        ]
        
        # 调用API
        response = self.client.get("/api/positions/status?date=20240101")
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["ts_code"], "000001.SZ")
        self.assertEqual(data[1]["ts_code"], "000002.SZ")
        
        mock_get_all_positions.assert_called_once_with("20240101")

    def test_api_invalid_date_format(self):
        """测试无效日期格式"""
        response = self.client.get("/api/signals/current-status?date=2024-01-01")
        self.assertEqual(response.status_code, 422)  # 验证失败
        
        response = self.client.get("/api/positions/status?date=invalid")
        self.assertEqual(response.status_code, 422)  # 验证失败


if __name__ == '__main__':
    unittest.main()
"""
测试 position_status_svc.py 中的所有业务逻辑功能
"""
import unittest
from unittest.mock import patch, MagicMock
from backend.services.position_status_svc import PositionStatusService


class TestPositionStatusService(unittest.TestCase):

    def setUp(self):
        """测试前准备"""
        pass

    def tearDown(self):
        """测试后清理"""
        pass

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_normal(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试正常范围内的持仓状态计算"""
        # 设置mock返回值
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,  # 20%
            'stop_loss_pct': 10.0   # 10%
        }
        
        # 模拟持仓数据：持仓1000股，成本10元，当前价11元（+10%收益）
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000001.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 10.0,
                'eod_close': 11.0
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        # 执行测试
        result = PositionStatusService.get_current_position_status("20240101")
        
        # 验证结果
        self.assertEqual(len(result), 1)
        position = result[0]
        self.assertEqual(position['ts_code'], '000001.SZ')
        self.assertEqual(position['shares'], 1000.0)
        self.assertEqual(position['avg_cost'], 10.0)
        self.assertEqual(position['current_price'], 11.0)
        self.assertAlmostEqual(position['return_rate'], 0.1, places=4)  # 10%
        self.assertEqual(position['status'], 'NORMAL')
        self.assertEqual(position['stop_gain_threshold'], 0.2)
        self.assertEqual(position['stop_loss_threshold'], 0.1)
        self.assertFalse(position['price_fallback_used'])

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_stop_gain(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试止盈状态的持仓计算"""
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,
            'stop_loss_pct': 10.0
        }
        
        # 模拟持仓数据：成本10元，当前价12.5元（+25%收益，超过20%止盈线）
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000002.SZ',
                'category_id': 1,
                'shares': 500.0,
                'avg_cost': 10.0,
                'eod_close': 12.5
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        result = PositionStatusService.get_current_position_status("20240101")
        
        self.assertEqual(len(result), 1)
        position = result[0]
        self.assertEqual(position['status'], 'STOP_GAIN')
        self.assertAlmostEqual(position['return_rate'], 0.25, places=4)  # 25%
        self.assertIn("达到止盈目标", position['message'])
        self.assertIn("25.00%", position['message'])

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_stop_loss(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试止损状态的持仓计算"""
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,
            'stop_loss_pct': 10.0
        }
        
        # 模拟持仓数据：成本10元，当前价8.5元（-15%收益，超过-10%止损线）
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000003.SZ',
                'category_id': 2,
                'shares': 800.0,
                'avg_cost': 10.0,
                'eod_close': 8.5
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        result = PositionStatusService.get_current_position_status("20240101")
        
        self.assertEqual(len(result), 1)
        position = result[0]
        self.assertEqual(position['status'], 'STOP_LOSS')
        self.assertAlmostEqual(position['return_rate'], -0.15, places=4)  # -15%
        self.assertIn("触发止损阈值", position['message'])
        self.assertIn("-15.00%", position['message'])

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_price_fallback(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试价格缺失时使用成本价作为fallback的情况"""
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,
            'stop_loss_pct': 10.0
        }
        
        # 模拟数据：价格为None（新标的未同步价格）
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000004.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 15.0,
                'eod_close': None  # 价格缺失
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        result = PositionStatusService.get_current_position_status("20240101")
        
        self.assertEqual(len(result), 1)
        position = result[0]
        self.assertEqual(position['current_price'], 15.0)  # 使用avg_cost作为fallback
        self.assertEqual(position['return_rate'], 0.0)     # 收益率为0
        self.assertEqual(position['status'], 'NORMAL')
        self.assertTrue(position['price_fallback_used'])

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_filter_by_ts_code(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试按ts_code过滤持仓状态"""
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,
            'stop_loss_pct': 10.0
        }
        
        # 模拟多个持仓数据
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000001.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 10.0,
                'eod_close': 11.0
            },
            {
                'ts_code': '000002.SZ',
                'category_id': 1,
                'shares': 500.0,
                'avg_cost': 20.0,
                'eod_close': 25.0
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        # 测试过滤特定ts_code
        result = PositionStatusService.get_current_position_status("20240101", "000002.SZ")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ts_code'], '000002.SZ')

    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_get_current_position_status_skip_invalid_positions(self, mock_get_conn, mock_reporting_repo, mock_get_config):
        """测试跳过无效持仓数据"""
        mock_get_config.return_value = {
            'stop_gain_pct': 20.0,
            'stop_loss_pct': 10.0
        }
        
        # 模拟包含无效数据的持仓
        mock_reporting_repo.return_value = [
            {
                'ts_code': '000001.SZ',
                'category_id': 1,
                'shares': 0.0,        # 无持仓
                'avg_cost': 10.0,
                'eod_close': 11.0
            },
            {
                'ts_code': '000002.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 0.0,      # 无效成本
                'eod_close': 11.0
            },
            {
                'ts_code': None,      # 无效ts_code
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 10.0,
                'eod_close': 11.0
            },
            {
                'ts_code': '000004.SZ',
                'category_id': 1,
                'shares': 1000.0,
                'avg_cost': 10.0,
                'eod_close': 11.0
            }
        ]
        
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        result = PositionStatusService.get_current_position_status("20240101")
        
        # 只应该返回一个有效的持仓
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ts_code'], '000004.SZ')

    def test_determine_status_stop_gain(self):
        """测试状态判断逻辑：止盈"""
        status, message = PositionStatusService._determine_status("000001.SZ", 0.25, 0.2, 0.1)
        self.assertEqual(status, "STOP_GAIN")
        self.assertIn("达到止盈目标", message)
        self.assertIn("25.00%", message)
        self.assertIn("20%", message)

    def test_determine_status_stop_loss(self):
        """测试状态判断逻辑：止损"""
        status, message = PositionStatusService._determine_status("000001.SZ", -0.12, 0.2, 0.1)
        self.assertEqual(status, "STOP_LOSS")
        self.assertIn("触发止损阈值", message)
        self.assertIn("-12.00%", message)
        self.assertIn("-10%", message)

    def test_determine_status_normal(self):
        """测试状态判断逻辑：正常"""
        status, message = PositionStatusService._determine_status("000001.SZ", 0.05, 0.2, 0.1)
        self.assertEqual(status, "NORMAL")
        self.assertIn("正常范围内", message)
        self.assertIn("5.00%", message)

    def test_determine_status_edge_cases(self):
        """测试边界情况"""
        # 正好达到止盈线
        status, message = PositionStatusService._determine_status("000001.SZ", 0.2, 0.2, 0.1)
        self.assertEqual(status, "STOP_GAIN")
        
        # 正好达到止损线
        status, message = PositionStatusService._determine_status("000001.SZ", -0.1, 0.2, 0.1)
        self.assertEqual(status, "STOP_LOSS")

    @patch('backend.services.position_status_svc.PositionStatusService.get_current_position_status')
    def test_get_position_alerts_count(self, mock_get_position_status):
        """测试持仓状态统计"""
        # 模拟多种状态的持仓
        mock_get_position_status.return_value = [
            {'status': 'STOP_GAIN'},
            {'status': 'STOP_GAIN'},
            {'status': 'STOP_LOSS'},
            {'status': 'NORMAL'},
            {'status': 'NORMAL'},
            {'status': 'NORMAL'}
        ]
        
        result = PositionStatusService.get_position_alerts_count("20240101")
        
        expected = {"stop_gain": 2, "stop_loss": 1, "normal": 3}
        self.assertEqual(result, expected)

    @patch('backend.services.position_status_svc.PositionStatusService.get_current_position_status')
    def test_get_position_status_by_instrument_found(self, mock_get_position_status):
        """测试获取特定标的的持仓状态 - 找到"""
        mock_get_position_status.return_value = [
            {'ts_code': '000001.SZ', 'status': 'NORMAL', 'return_rate': 0.05}
        ]
        
        result = PositionStatusService.get_position_status_by_instrument("000001.SZ", "20240101")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['ts_code'], '000001.SZ')
        mock_get_position_status.assert_called_once_with("20240101", "000001.SZ")

    @patch('backend.services.position_status_svc.PositionStatusService.get_current_position_status')
    def test_get_position_status_by_instrument_not_found(self, mock_get_position_status):
        """测试获取特定标的的持仓状态 - 未找到"""
        mock_get_position_status.return_value = []
        
        result = PositionStatusService.get_position_status_by_instrument("999999.SZ", "20240101")
        
        self.assertIsNone(result)

    @patch('backend.services.position_status_svc.datetime')
    @patch('backend.services.position_status_svc.config_svc.get_config')
    @patch('backend.services.position_status_svc.reporting_repo.active_instruments_with_pos_and_price')
    @patch('backend.services.position_status_svc.get_conn')
    def test_default_date_handling(self, mock_get_conn, mock_reporting_repo, mock_get_config, mock_datetime):
        """测试默认日期处理"""
        # 模拟今天的日期
        mock_datetime.now.return_value.strftime.return_value = "20240315"
        mock_get_config.return_value = {'stop_gain_pct': 20.0, 'stop_loss_pct': 10.0}
        mock_reporting_repo.return_value = []
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        PositionStatusService.get_current_position_status()
        
        # 验证使用了正确的日期格式调用了数据库查询
        mock_reporting_repo.assert_called_once_with(mock_conn, "2024-03-15")


if __name__ == '__main__':
    unittest.main()
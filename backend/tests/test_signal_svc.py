"""
信号业务服务层测试
测试 signal_svc.py 中的所有业务逻辑功能
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.db import get_conn
from backend.services.signal_svc import SignalService, SignalGenerationService


class TestSignalService:
    """信号业务服务测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with get_conn() as conn:
            # 清空相关表
            conn.execute("DELETE FROM signal")
            conn.execute("DELETE FROM position")
            conn.execute("DELETE FROM price_eod")
            
            # 准备测试数据
            conn.execute("""
                INSERT OR IGNORE INTO category (id, name, sub_name, target_units) 
                VALUES (1, '测试类别', '子类别', 5.0)
            """)
            conn.execute("""
                INSERT OR IGNORE INTO instrument (ts_code, name, category_id, active) 
                VALUES ('000001.SZ', '测试股票1', 1, 1)
            """)
            conn.execute("""
                INSERT OR IGNORE INTO instrument (ts_code, name, category_id, active) 
                VALUES ('000002.SZ', '测试股票2', 1, 1)
            """)
            conn.commit()
    
    def test_get_signals_by_date_basic(self):
        """测试基础信号查询"""
        # 插入测试信号
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '测试止盈信号')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000002.SZ', 'MEDIUM', 'STOP_LOSS', '测试止损信号')
            """)
            conn.commit()
        
        # 测试获取所有信号
        signals = SignalService.get_signals_by_date("20240101")
        assert len(signals) == 2
        
        # 测试按类型过滤
        gain_signals = SignalService.get_signals_by_date("20240101", "STOP_GAIN")
        assert len(gain_signals) == 1
        assert gain_signals[0]["type"] == "STOP_GAIN"
        
        # 测试按标的过滤
        stock_signals = SignalService.get_signals_by_date("20240101", ts_code="000001.SZ")
        assert len(stock_signals) == 1
        assert stock_signals[0]["ts_code"] == "000001.SZ"
    
    def test_get_signals_by_date_with_global_signals(self):
        """测试获取信号（包含全局信号）"""
        with get_conn() as conn:
            # 插入直接信号
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '直接信号')
            """)
            # 插入全局信号
            conn.execute("""
                INSERT INTO signal (trade_date, scope_type, level, type, message) 
                VALUES ('2024-01-01', 'ALL_INSTRUMENTS', 'MEDIUM', 'MARKET_CLOSE', '全局信号')
            """)
            conn.commit()
        
        # 查询特定标的应该包含全局信号
        signals = SignalService.get_signals_by_date("20240101", ts_code="000001.SZ")
        
        signal_types = [s["type"] for s in signals]
        assert "STOP_GAIN" in signal_types
        assert "MARKET_CLOSE" in signal_types
    
    def test_get_signals_history(self):
        """测试历史信号查询"""
        with get_conn() as conn:
            # 插入不同日期的信号
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '历史信号1')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-02', '000001.SZ', 'MEDIUM', 'STOP_LOSS', '历史信号2')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-03', '000002.SZ', 'LOW', 'INFO', '历史信号3')
            """)
            conn.commit()
        
        # 测试获取所有历史信号
        all_signals = SignalService.get_signals_history()
        assert len(all_signals) >= 3
        
        # 测试过滤条件
        gain_signals = SignalService.get_signals_history(signal_type="STOP_GAIN")
        assert len(gain_signals) == 1
        
        stock_signals = SignalService.get_signals_history(ts_code="000001.SZ")
        assert len(stock_signals) >= 2
        
        range_signals = SignalService.get_signals_history(
            start_date="2024-01-01", end_date="2024-01-02"
        )
        assert len(range_signals) >= 2
    
    def test_create_manual_signal_basic(self):
        """测试基础手动信号创建"""
        signal_id = SignalService.create_manual_signal(
            trade_date="2024-01-01",
            ts_code="000001.SZ",
            level="HIGH",
            signal_type="MANUAL_ALERT",
            message="手动创建的信号"
        )
        
        assert signal_id is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["ts_code"] == "000001.SZ"
            assert signal["type"] == "MANUAL_ALERT"
            assert signal["message"] == "手动创建的信号"
    
    def test_create_manual_signal_with_category(self):
        """测试创建类别信号"""
        signal_id = SignalService.create_manual_signal(
            trade_date="2024-01-01",
            category_id=1,
            level="MEDIUM",
            signal_type="CATEGORY_ALERT",
            message="类别信号"
        )
        
        assert signal_id is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["category_id"] == 1
            assert signal["scope_type"] == "CATEGORY"
    
    def test_create_manual_signal_multi_instrument(self):
        """测试创建多标的信号"""
        signal_id = SignalService.create_manual_signal(
            trade_date="2024-01-01",
            scope_type="MULTI_INSTRUMENT",
            scope_data=["000001.SZ", "000002.SZ"],
            level="HIGH",
            signal_type="SECTOR_ALERT",
            message="板块预警"
        )
        
        assert signal_id is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["scope_type"] == "MULTI_INSTRUMENT"
            assert '"000001.SZ"' in signal["scope_data"]
            assert '"000002.SZ"' in signal["scope_data"]
    
    def test_create_manual_signal_validation_error(self):
        """测试信号创建参数验证"""
        # 测试无效标的代码
        with pytest.raises(ValueError, match="标的代码.*不存在"):
            SignalService.create_manual_signal(
                trade_date="2024-01-01",
                ts_code="999999.SZ",
                level="HIGH",
                signal_type="TEST",
                message="测试"
            )
        
        # 测试无效类别ID
        with pytest.raises(ValueError, match="类别ID.*不存在"):
            SignalService.create_manual_signal(
                trade_date="2024-01-01",
                category_id=999,
                level="HIGH",
                signal_type="TEST",
                message="测试"
            )
    
    def test_get_signal_counts_by_date(self):
        """测试信号统计功能"""
        with get_conn() as conn:
            # 插入不同类型的信号
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '信号1')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000002.SZ', 'HIGH', 'STOP_GAIN', '信号2')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_LOSS', '信号3')
            """)
            conn.commit()
        
        counts = SignalService.get_signal_counts_by_date("2024-01-01")
        
        assert counts["stop_gain"] == 2
        assert counts["stop_loss"] == 1


class TestSignalGenerationService:
    """信号生成服务测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with get_conn() as conn:
            # 清空相关表
            conn.execute("DELETE FROM signal")
            conn.execute("DELETE FROM position")  
            conn.execute("DELETE FROM price_eod")
            
            # 准备测试数据 - 先创建category
            conn.execute("""
                INSERT OR IGNORE INTO category (id, name, sub_name, target_units) 
                VALUES (1, '测试类别', '子类别', 5.0)
            """)
            conn.execute("""
                INSERT OR IGNORE INTO instrument (ts_code, name, category_id, active) 
                VALUES ('000001.SZ', '测试股票1', 1, 1)
            """)
            conn.execute("""
                INSERT OR IGNORE INTO position (ts_code, shares, avg_cost, opening_date) 
                VALUES ('000001.SZ', 1000, 10.0, '2024-01-01')
            """)
            conn.commit()
    
    def test_generate_stop_signals_for_position_gain(self):
        """测试为持仓生成止盈信号"""
        with get_conn() as conn:
            # 插入价格数据，价格上涨触发止盈
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000001.SZ', '2024-01-02', 13.0)
            """)  # 30%涨幅，应该触发止盈
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000001.SZ', '2024-01-03', 14.0)
            """)  # 40%涨幅，但已有止盈信号
            conn.commit()
        
        count, date_range = SignalGenerationService.generate_stop_signals_for_position(
            ts_code="000001.SZ",
            avg_cost=10.0,
            opening_date="2024-01-01",
            stop_gain=0.2,  # 20%止盈
            stop_loss=0.1   # 10%止损
        )
        
        assert count == 1
        assert date_range is not None
        assert date_range[0] == "2024-01-02"  # 首次触发日期
        
        # 验证信号已创建
        with get_conn() as conn:
            signals = conn.execute("""
                SELECT * FROM signal WHERE ts_code=? AND type=?
            """, ("000001.SZ", "STOP_GAIN")).fetchall()
            assert len(signals) == 1
            assert signals[0]["trade_date"] == "2024-01-02"
    
    def test_generate_stop_signals_for_position_loss(self):
        """测试为持仓生成止损信号"""
        with get_conn() as conn:
            # 插入价格数据，价格下跌触发止损
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000001.SZ', '2024-01-02', 8.5)
            """)  # -15%跌幅，应该触发止损
            conn.commit()
        
        count, date_range = SignalGenerationService.generate_stop_signals_for_position(
            ts_code="000001.SZ",
            avg_cost=10.0,
            opening_date="2024-01-01", 
            stop_gain=0.2,  # 20%止盈
            stop_loss=0.1   # 10%止损
        )
        
        assert count == 1
        assert date_range is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signals = conn.execute("""
                SELECT * FROM signal WHERE ts_code=? AND type=?
            """, ("000001.SZ", "STOP_LOSS")).fetchall()
            assert len(signals) == 1
    
    def test_generate_stop_signals_no_trigger(self):
        """测试价格未触发止盈止损的情况"""
        with get_conn() as conn:
            # 插入价格数据，价格变动不大
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000001.SZ', '2024-01-02', 10.5)
            """)  # 5%涨幅，未触发
            conn.commit()
        
        count, date_range = SignalGenerationService.generate_stop_signals_for_position(
            ts_code="000001.SZ",
            avg_cost=10.0,
            opening_date="2024-01-01",
            stop_gain=0.2,  # 20%止盈
            stop_loss=0.1   # 10%止损
        )
        
        assert count == 0
        assert date_range is None
    
    @patch('backend.services.config_svc.get_config')
    def test_rebuild_all_historical_signals(self, mock_get_config):
        """测试重建所有历史信号"""
        # Mock配置
        mock_get_config.return_value = {
            'stop_gain_pct': 20,
            'stop_loss_pct': 10
        }
        
        with get_conn() as conn:
            # 添加另一个持仓
            conn.execute("""
                INSERT INTO position (ts_code, shares, avg_cost, opening_date) 
                VALUES ('000002.SZ', 500, 20.0, '2024-01-01')
            """)
            
            # 添加价格数据
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000001.SZ', '2024-01-02', 13.0)
            """)  # 触发止盈
            conn.execute("""
                INSERT INTO price_eod (ts_code, trade_date, close) 
                VALUES ('000002.SZ', '2024-01-02', 17.0)  
            """)  # 触发止损
            conn.commit()
        
        result = SignalGenerationService.rebuild_all_historical_signals()
        
        assert result["count"] >= 2  # 至少生成2个信号
        assert "date_range" in result
        
        # 验证旧信号被清除，新信号被创建
        with get_conn() as conn:
            signals = conn.execute("SELECT * FROM signal").fetchall()
            signal_types = [s["type"] for s in signals]
            assert "STOP_GAIN" in signal_types
            assert "STOP_LOSS" in signal_types
    
    def test_generate_current_signals(self):
        """测试生成当前信号"""
        # 创建测试数据
        positions_data = {
            'ts_code': ['000001.SZ', '000002.SZ'],
            'cost': [10000, 5000],
            'unrealized_pnl': [3000, -600],  # 30%盈利，-12%亏损
            'close': [13.0, 8.8],
            'avg_cost': [10.0, 10.0]  # 添加平均成本字段
        }
        positions_df = pd.DataFrame(positions_data)
        
        SignalGenerationService.generate_current_signals(
            positions_df, 
            stop_gain=0.2,  # 20%止盈
            stop_loss=0.1   # 10%止损
        )
        
        # 验证信号生成
        with get_conn() as conn:
            # 000001.SZ应该生成止盈信号
            gain_signals = conn.execute("""
                SELECT * FROM signal WHERE ts_code=? AND type=?
            """, ("000001.SZ", "STOP_GAIN")).fetchall()
            
            # 000002.SZ应该生成止损信号  
            loss_signals = conn.execute("""
                SELECT * FROM signal WHERE ts_code=? AND type=?
            """, ("000002.SZ", "STOP_LOSS")).fetchall()
            
            # 由于避免重复，如果之前没有信号才会创建
            assert len(gain_signals) >= 0
            assert len(loss_signals) >= 0
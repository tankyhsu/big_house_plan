"""
Dashboard服务信号功能集成测试
测试 dashboard_svc.py 中的信号相关功能，确保重构后的向后兼容性
"""
from __future__ import annotations


import pytest
from backend.db import get_conn
from backend.services import dashboard_svc


class TestDashboardSignalIntegration:
    """Dashboard信号功能集成测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with get_conn() as conn:
            # 清空相关表
            conn.execute("DELETE FROM signal")
            
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
    
    def test_list_signal_backward_compatibility(self):
        """测试list_signal函数的向后兼容性"""
        # 插入测试信号
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '测试信号1')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000002.SZ', 'MEDIUM', 'STOP_LOSS', '测试信号2')
            """)
            conn.commit()
        
        # 测试基础功能
        signals = dashboard_svc.list_signal("20240101")
        assert len(signals) == 2
        
        # 测试类型过滤
        gain_signals = dashboard_svc.list_signal("20240101", typ="STOP_GAIN")
        assert len(gain_signals) == 1
        assert gain_signals[0]["type"] == "STOP_GAIN"
        
        # 测试标的过滤
        stock_signals = dashboard_svc.list_signal("20240101", ts_code="000001.SZ")
        assert len(stock_signals) == 1
        assert stock_signals[0]["ts_code"] == "000001.SZ"
    
    def test_list_signal_all_backward_compatibility(self):
        """测试list_signal_all函数的向后兼容性"""
        # 插入测试信号
        with get_conn() as conn:
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
        all_signals = dashboard_svc.list_signal_all()
        assert len(all_signals) >= 3
        
        # 测试类型过滤
        gain_signals = dashboard_svc.list_signal_all(typ="STOP_GAIN")
        assert len(gain_signals) == 1
        
        # 测试标的过滤  
        stock_signals = dashboard_svc.list_signal_all(ts_code="000001.SZ")
        assert len(stock_signals) >= 2
        
        # 测试日期范围过滤
        range_signals = dashboard_svc.list_signal_all(
            start_date="2024-01-01", end_date="2024-01-02"
        )
        assert len(range_signals) >= 2
        
        # 测试数量限制
        limited_signals = dashboard_svc.list_signal_all(limit=2)
        assert len(limited_signals) <= 2
    
    def test_create_manual_signal_backward_compatibility(self):
        """测试create_manual_signal函数的向后兼容性"""
        # 测试创建标的信号
        signal_id = dashboard_svc.create_manual_signal(
            trade_date="2024-01-01",
            ts_code="000001.SZ", 
            category_id=None,
            level="HIGH",
            type="MANUAL_ALERT",
            message="手动创建的标的信号"
        )
        
        assert signal_id is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["ts_code"] == "000001.SZ"
            assert signal["type"] == "MANUAL_ALERT"
        
        # 测试创建类别信号
        signal_id2 = dashboard_svc.create_manual_signal(
            trade_date="2024-01-01",
            ts_code=None,
            category_id=1,
            level="MEDIUM", 
            type="CATEGORY_ALERT",
            message="手动创建的类别信号"
        )
        
        assert signal_id2 is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id2,)).fetchone()
            assert signal is not None
            assert signal["category_id"] == 1
            assert signal["type"] == "CATEGORY_ALERT"
    
    def test_create_manual_signal_extended_backward_compatibility(self):
        """测试create_manual_signal_extended函数的向后兼容性"""
        # 测试多标的信号创建
        signal_id = dashboard_svc.create_manual_signal_extended(
            trade_date="2024-01-01",
            ts_code=None,
            category_id=None,
            scope_type="MULTI_INSTRUMENT",
            scope_data=["000001.SZ", "000002.SZ"],
            level="HIGH",
            type="SECTOR_ALERT",
            message="板块预警信号"
        )
        
        assert signal_id is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["scope_type"] == "MULTI_INSTRUMENT"
            assert '"000001.SZ"' in signal["scope_data"]
            assert '"000002.SZ"' in signal["scope_data"]
        
        # 测试全局信号创建
        signal_id2 = dashboard_svc.create_manual_signal_extended(
            trade_date="2024-01-01",
            ts_code=None,
            category_id=None,
            scope_type="ALL_INSTRUMENTS",
            scope_data=None,
            level="MEDIUM",
            type="MARKET_CLOSE",
            message="全市场休市通知"
        )
        
        assert signal_id2 is not None
        
        # 验证信号已创建
        with get_conn() as conn:
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id2,)).fetchone()
            assert signal is not None
            assert signal["scope_type"] == "ALL_INSTRUMENTS"
            assert signal["type"] == "MARKET_CLOSE"
    
    def test_get_dashboard_signal_counts(self):
        """测试get_dashboard中的信号统计功能"""
        # 插入不同类型的信号
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '止盈信号1')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000002.SZ', 'HIGH', 'STOP_GAIN', '止盈信号2')
            """)
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_LOSS', '止损信号1')
            """)
            
            # 准备position和instrument数据以避免get_dashboard出错
            conn.execute("""
                INSERT OR IGNORE INTO position (ts_code, shares, avg_cost) 
                VALUES ('000001.SZ', 100, 10.0)
            """)
            conn.commit()
        
        # 调用get_dashboard应该包含正确的信号统计
        dashboard_data = dashboard_svc.get_dashboard("20240101")
        
        assert "signals" in dashboard_data
        assert dashboard_data["signals"]["stop_gain"] == 2
        assert dashboard_data["signals"]["stop_loss"] == 1
    
    def test_signal_scope_matching_with_global_signals(self):
        """测试全局信号的范围匹配功能"""
        with get_conn() as conn:
            # 插入全局信号
            conn.execute("""
                INSERT INTO signal (trade_date, scope_type, level, type, message) 
                VALUES ('2024-01-01', 'ALL_INSTRUMENTS', 'HIGH', 'MARKET_CLOSE', '全市场休市')
            """)
            # 插入类别全局信号
            conn.execute("""
                INSERT INTO signal (trade_date, scope_type, level, type, message) 
                VALUES ('2024-01-01', 'ALL_CATEGORIES', 'MEDIUM', 'SECTOR_NEWS', '行业消息')
            """)
            conn.commit()
        
        # 查询特定标的应该包含全局信号
        signals = dashboard_svc.list_signal("20240101", ts_code="000001.SZ")
        
        signal_types = [s["type"] for s in signals]
        assert "MARKET_CLOSE" in signal_types  # ALL_INSTRUMENTS信号应该被包含
        assert "SECTOR_NEWS" in signal_types   # ALL_CATEGORIES信号应该被包含
    
    def test_signal_validation_errors(self):
        """测试信号创建的验证错误"""
        # 测试无效标的代码
        with pytest.raises(ValueError, match="标的代码.*不存在"):
            dashboard_svc.create_manual_signal(
                trade_date="2024-01-01",
                ts_code="999999.SZ",
                category_id=None,
                level="HIGH",
                type="TEST",
                message="测试"
            )
        
        # 测试无效类别ID
        with pytest.raises(ValueError, match="类别ID.*不存在"):
            dashboard_svc.create_manual_signal(
                trade_date="2024-01-01",
                ts_code=None,
                category_id=999,
                level="HIGH",
                type="TEST", 
                message="测试"
            )
    
    def test_signal_functions_return_format(self):
        """测试信号函数返回格式的一致性"""
        # 插入测试数据
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO signal (trade_date, ts_code, level, type, message) 
                VALUES ('2024-01-01', '000001.SZ', 'HIGH', 'STOP_GAIN', '格式测试')
            """)
            conn.commit()
        
        # 测试list_signal返回格式
        signals = dashboard_svc.list_signal("20240101")
        assert isinstance(signals, list)
        if signals:
            signal = signals[0]
            assert isinstance(signal, dict)
            assert "id" in signal
            assert "trade_date" in signal
            assert "ts_code" in signal
            assert "level" in signal
            assert "type" in signal
            assert "message" in signal
        
        # 测试list_signal_all返回格式
        all_signals = dashboard_svc.list_signal_all()
        assert isinstance(all_signals, list)
        if all_signals:
            signal = all_signals[0]
            assert isinstance(signal, dict)
            # 历史信号应该包含name字段（JOIN instrument表）
            assert "name" in signal or signal["ts_code"] is None  # 全局信号可能没有name
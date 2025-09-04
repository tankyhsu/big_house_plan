"""
信号仓储层测试
测试 signal_repo.py 中的所有数据访问功能
"""

import pytest
from backend.db import get_conn
from backend.repository import signal_repo


class TestSignalRepo:
    """信号仓储层测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        with get_conn() as conn:
            # 清空信号表
            conn.execute("DELETE FROM signal")
            # 确保有测试数据的标的和类别
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
    
    def test_insert_signal_basic(self):
        """测试基本信号插入"""
        with get_conn() as conn:
            signal_id = signal_repo.insert_signal(
                conn, 
                trade_date="2024-01-01",
                ts_code="000001.SZ", 
                level="HIGH", 
                signal_type="STOP_GAIN", 
                message="测试止盈信号"
            )
            
            assert signal_id is not None
            
            # 验证插入的数据
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal is not None
            assert signal["ts_code"] == "000001.SZ"
            assert signal["level"] == "HIGH"
            assert signal["type"] == "STOP_GAIN"
            assert signal["message"] == "测试止盈信号"
    
    def test_insert_signal_with_scope_data(self):
        """测试带范围数据的信号插入"""
        with get_conn() as conn:
            signal_id = signal_repo.insert_signal(
                conn,
                trade_date="2024-01-01",
                scope_type="MULTI_INSTRUMENT",
                scope_data=["000001.SZ", "000002.SZ"],
                level="MEDIUM",
                signal_type="MARKET_ALERT",
                message="市场预警信号"
            )
            
            assert signal_id is not None
            
            # 验证数据
            signal = conn.execute("SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            assert signal["scope_type"] == "MULTI_INSTRUMENT"
            assert '"000001.SZ"' in signal["scope_data"]
            assert '"000002.SZ"' in signal["scope_data"]
    
    def test_insert_signal_if_not_exists(self):
        """测试避免重复插入的信号创建"""
        with get_conn() as conn:
            # 第一次插入应该成功
            signal_id1 = signal_repo.insert_signal_if_not_exists(
                conn, "2024-01-01", "000001.SZ", "HIGH", "STOP_GAIN", "第一次测试"
            )
            assert signal_id1 is not None
            
            # 第二次插入相同类型应该返回None
            signal_id2 = signal_repo.insert_signal_if_not_exists(
                conn, "2024-01-01", "000001.SZ", "HIGH", "STOP_GAIN", "第二次测试"
            )
            assert signal_id2 is None
            
            # 不同类型应该可以插入
            signal_id3 = signal_repo.insert_signal_if_not_exists(
                conn, "2024-01-01", "000001.SZ", "HIGH", "STOP_LOSS", "不同类型测试"
            )
            assert signal_id3 is not None
    
    def test_get_signals_by_date(self):
        """测试按日期获取信号"""
        with get_conn() as conn:
            # 插入测试数据
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="信号1")
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000002.SZ", level="MEDIUM", 
                                    signal_type="STOP_LOSS", message="信号2")
            signal_repo.insert_signal(conn, "2024-01-02", ts_code="000001.SZ", level="LOW", 
                                    signal_type="INFO", message="信号3")
            
            # 测试获取特定日期的所有信号
            signals = signal_repo.get_signals_by_date(conn, "2024-01-01")
            assert len(signals) == 2
            
            # 测试按类型过滤
            gain_signals = signal_repo.get_signals_by_date(conn, "2024-01-01", "STOP_GAIN")
            assert len(gain_signals) == 1
            assert gain_signals[0]["type"] == "STOP_GAIN"
            
            # 测试按标的过滤
            stock_signals = signal_repo.get_signals_by_date(conn, "2024-01-01", ts_code="000001.SZ")
            assert len(stock_signals) == 1
            assert stock_signals[0]["ts_code"] == "000001.SZ"
    
    def test_get_signals_for_instrument(self):
        """测试获取特定标的相关信号（包括全局信号）"""
        with get_conn() as conn:
            # 插入不同类型的信号
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="直接信号")
            signal_repo.insert_signal(conn, "2024-01-01", scope_type="ALL_INSTRUMENTS", 
                                    level="MEDIUM", signal_type="MARKET_CLOSE", message="全局信号")
            signal_repo.insert_signal(conn, "2024-01-01", scope_type="MULTI_INSTRUMENT",
                                    scope_data=["000001.SZ", "000002.SZ"], level="LOW",
                                    signal_type="SECTOR_ALERT", message="多标的信号")
            
            # 获取000001.SZ相关的所有信号
            signals = signal_repo.get_signals_for_instrument(conn, "000001.SZ", "2024-01-01")
            
            # 应该包含直接信号、全局信号和多标的信号
            assert len(signals) >= 3
            signal_types = [s["type"] for s in signals]
            assert "STOP_GAIN" in signal_types
            assert "MARKET_CLOSE" in signal_types
            assert "SECTOR_ALERT" in signal_types
    
    def test_get_signals_history(self):
        """测试获取历史信号记录"""
        with get_conn() as conn:
            # 插入不同日期的信号
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="历史信号1")
            signal_repo.insert_signal(conn, "2024-01-02", ts_code="000001.SZ", level="MEDIUM", 
                                    signal_type="STOP_LOSS", message="历史信号2")
            signal_repo.insert_signal(conn, "2024-01-03", ts_code="000002.SZ", level="LOW", 
                                    signal_type="INFO", message="历史信号3")
            
            # 测试获取所有历史信号
            all_signals = signal_repo.get_signals_history(conn)
            assert len(all_signals) >= 3
            
            # 测试按类型过滤
            gain_signals = signal_repo.get_signals_history(conn, signal_type="STOP_GAIN")
            assert len(gain_signals) == 1
            assert gain_signals[0]["type"] == "STOP_GAIN"
            
            # 测试按标的过滤
            stock_signals = signal_repo.get_signals_history(conn, ts_code="000001.SZ")
            assert len(stock_signals) >= 2
            
            # 测试日期范围过滤
            range_signals = signal_repo.get_signals_history(
                conn, start_date="2024-01-01", end_date="2024-01-02"
            )
            assert len(range_signals) >= 2
            
            # 测试限制数量
            limited_signals = signal_repo.get_signals_history(conn, limit=2)
            assert len(limited_signals) <= 2
    
    def test_delete_signals_by_type(self):
        """测试按类型删除信号"""
        with get_conn() as conn:
            # 插入不同类型的信号
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="删除测试1")
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_LOSS", message="删除测试2")
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="INFO", 
                                    signal_type="MANUAL", message="保留测试")
            
            # 删除止盈止损信号
            deleted_count = signal_repo.delete_signals_by_type(conn, ["STOP_GAIN", "STOP_LOSS"])
            assert deleted_count == 2
            
            # 验证删除结果
            remaining_signals = signal_repo.get_signals_by_date(conn, "2024-01-01")
            assert len(remaining_signals) == 1
            assert remaining_signals[0]["type"] == "MANUAL"
    
    def test_get_signal_counts_by_date(self):
        """测试获取信号统计数量"""
        with get_conn() as conn:
            # 插入不同类型的信号
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="统计测试1")
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000002.SZ", level="HIGH", 
                                    signal_type="STOP_GAIN", message="统计测试2")
            signal_repo.insert_signal(conn, "2024-01-01", ts_code="000001.SZ", level="HIGH", 
                                    signal_type="STOP_LOSS", message="统计测试3")
            
            # 获取统计数量
            counts = signal_repo.get_signal_counts_by_date(conn, "2024-01-01")
            
            assert counts["stop_gain"] == 2
            assert counts["stop_loss"] == 1
    
    def test_validate_instrument_codes(self):
        """测试标的代码验证"""
        with get_conn() as conn:
            # 测试已存在的代码
            invalid_codes = signal_repo.validate_instrument_codes(conn, ["000001.SZ", "000002.SZ"])
            assert len(invalid_codes) == 0
            
            # 测试不存在的代码
            invalid_codes = signal_repo.validate_instrument_codes(conn, ["000001.SZ", "999999.SZ"])
            assert len(invalid_codes) == 1
            assert "999999.SZ" in invalid_codes
    
    def test_validate_category_ids(self):
        """测试类别ID验证"""
        with get_conn() as conn:
            # 测试已存在的ID
            invalid_ids = signal_repo.validate_category_ids(conn, [1])
            assert len(invalid_ids) == 0
            
            # 测试不存在的ID
            invalid_ids = signal_repo.validate_category_ids(conn, [1, 999])
            assert len(invalid_ids) == 1
            assert 999 in invalid_ids
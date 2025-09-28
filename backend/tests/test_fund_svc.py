"""
基金服务层测试
测试 fund_svc.py 中的基金profile获取功能
"""
from __future__ import annotations

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from backend.services.fund_svc import fetch_fund_profile, clear_fund_profile_cache, _calculate_portfolio_changes, _get_recent_quarters


def test_get_recent_quarters():
    """测试获取最近季度函数"""
    quarters = _get_recent_quarters(18)
    assert len(quarters) == 6
    assert all(q.endswith(('0331', '0630', '0930', '1231')) for q in quarters)
    # Should be in descending order (most recent first)
    assert quarters == sorted(quarters, reverse=True)


def test_calculate_portfolio_changes_empty():
    """测试空数据的持仓变化计算"""
    changes = _calculate_portfolio_changes(None, None)
    assert changes == []

    empty_df = pd.DataFrame()
    changes = _calculate_portfolio_changes(empty_df, None)
    assert changes == []


def test_calculate_portfolio_changes_basic():
    """测试基础持仓变化计算"""
    current_df = pd.DataFrame([
        {'stock_code': '000001.SZ', 'stock_name': '平安银行', 'weight': 5.5, 'mkv': 50000, 'amount': 1000},
        {'stock_code': '000002.SZ', 'stock_name': '万科A', 'weight': 3.2, 'mkv': 30000, 'amount': 800}
    ])

    previous_df = pd.DataFrame([
        {'stock_code': '000001.SZ', 'stock_name': '平安银行', 'weight': 4.8, 'mkv': 45000, 'amount': 900}
    ])

    changes = _calculate_portfolio_changes(current_df, previous_df)

    assert len(changes) == 2

    # 平安银行 - 增持
    bank_change = next(c for c in changes if c['stock_code'] == '000001.SZ')
    assert bank_change['current_weight'] == 5.5
    assert bank_change['previous_weight'] == 4.8
    assert abs(bank_change['weight_change'] - 0.7) < 1e-10
    assert bank_change['is_increased'] == True
    assert bank_change['is_new'] == False

    # 万科A - 新增
    wanke_change = next(c for c in changes if c['stock_code'] == '000002.SZ')
    assert wanke_change['current_weight'] == 3.2
    assert wanke_change['previous_weight'] == 0
    assert wanke_change['weight_change'] == 3.2
    assert wanke_change['is_new'] == True


@patch('backend.services.fund_svc.get_config')
def test_fetch_fund_profile_no_token(mock_get_config):
    """测试无TuShare token的情况"""
    mock_get_config.return_value = {'tushare_token': None}

    result = fetch_fund_profile('000001.OF')

    assert result['holdings']['error'] == 'no_token'
    assert result['scale']['error'] == 'no_token'
    assert result['managers']['error'] == 'no_token'
"""
Test cases for enhanced cost calculation logic
"""
import pytest
from backend.domain.txn_engine import (
    compute_position_after_trade,
    compute_position_with_corporate_actions,
    calculate_cost_basis_adjustment
)


class TestEnhancedCostCalculation:
    """Test enhanced cost calculation with various scenarios"""

    def test_buy_transactions(self):
        """Test buy transactions with weighted average cost"""
        # Initial position: 100 shares at $10
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "BUY", 50, 12.0, 5.0)
        
        # Expected: 150 shares, avg cost = (100*10 + 50*12 + 5) / 150 = 1605/150 = 10.70
        assert shares == 150
        assert abs(cost - 10.70) < 0.01
        assert pnl == 0.0

    def test_sell_transactions(self):
        """Test sell transactions with realized P&L calculation"""
        # Sell 50 shares at $15 from position of 100 shares at $10 cost
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "SELL", 50, 15.0, 2.0)
        
        # Expected: 50 shares remaining, cost stays $10, realized P&L = (15-10)*50 - 2 = 248
        assert shares == 50
        assert cost == 10.0
        assert abs(pnl - 248.0) < 0.01

    def test_complete_sale(self):
        """Test complete position sale"""
        # Sell all 100 shares at $12
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "SELL", 100, 12.0, 1.0)
        
        # Expected: 0 shares, cost becomes 0, realized P&L = (12-10)*100 - 1 = 199
        assert shares == 0
        assert cost == 0.0
        assert abs(pnl - 199.0) < 0.01

    def test_cash_dividend(self):
        """Test cash dividend - no position change"""
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "DIV", 2.0, 0, 0)
        
        # Expected: position unchanged
        assert shares == 100
        assert cost == 10.0
        assert pnl == 0.0

    def test_stock_dividend(self):
        """Test stock dividend - 10% stock dividend"""
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "STOCK_DIV", 0.1, 0, 0)
        
        # Expected: 110 shares, cost adjusted to maintain same total value
        # New cost = 10.0 * 100 / 110 = 9.09
        assert shares == 110
        assert abs(cost - 9.09) < 0.01
        assert pnl == 0.0

    def test_stock_split(self):
        """Test 2:1 stock split"""
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "SPLIT", 2.0, 0, 0)
        
        # Expected: 200 shares at $5 each (same total value)
        assert shares == 200
        assert cost == 5.0
        assert pnl == 0.0

    def test_management_fee(self):
        """Test management fee adjustment"""
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "FEE", 0, 0, 50.0)
        
        # Expected: same shares, cost increased by $0.50 per share, negative P&L
        assert shares == 100
        assert cost == 10.5
        assert pnl == -50.0

    def test_multiple_transactions_sequence(self):
        """Test sequence of multiple transactions"""
        transactions = [
            {"action": "BUY", "qty": 100, "price": 10.0, "fee": 5.0},
            {"action": "BUY", "qty": 50, "price": 12.0, "fee": 3.0}, 
            {"action": "SELL", "qty": 30, "price": 15.0, "fee": 2.0},
            {"action": "STOCK_DIV", "qty": 0.05, "price": 0, "fee": 0},  # 5% stock dividend
        ]
        
        final_shares, final_cost, total_pnl = compute_position_with_corporate_actions(
            0, 0, transactions
        )
        
        # Step by step calculation:
        # 1. Buy 100 at 10: 100 shares, cost = (0 + 100*10 + 5)/100 = 10.05
        # 2. Buy 50 at 12: 150 shares, cost = (100*10.05 + 50*12 + 3)/150 = 10.72  
        # 3. Sell 30 at 15: 120 shares, cost = 10.72, pnl = (15-10.72)*30-2 = 126.4
        # 4. 5% stock dividend: 126 shares, cost = 10.72*120/126 = 10.21
        
        assert abs(final_shares - 126) < 0.1
        assert abs(final_cost - 10.21) < 0.05
        assert abs(total_pnl - 126.4) < 1.0

    def test_cost_basis_spinoff_adjustment(self):
        """Test spinoff cost basis adjustment"""
        # Allocate 30% of cost basis to spinoff
        adj_shares, adj_cost = calculate_cost_basis_adjustment(100, 10.0, "SPINOFF", 0.3)
        
        # Expected: same shares, cost reduced to $7 (70% of original)
        assert adj_shares == 100
        assert adj_cost == 7.0

    def test_cost_basis_merger_adjustment(self):
        """Test merger - position eliminated"""
        adj_shares, adj_cost = calculate_cost_basis_adjustment(100, 10.0, "MERGER", 1.0)
        
        # Expected: position eliminated
        assert adj_shares == 0.0
        assert adj_cost == 0.0

    def test_zero_position_handling(self):
        """Test handling of zero positions"""
        # Buy from zero position
        shares, cost, pnl = compute_position_after_trade(0, 0, "BUY", 100, 10.0, 5.0)
        
        # Expected: 100 shares at $10.05 cost (including fee)
        assert shares == 100
        assert cost == 10.05
        assert pnl == 0.0

    def test_negative_quantity_handling(self):
        """Test handling of negative quantities (short positions)"""
        # This should be handled by taking absolute value
        shares, cost, pnl = compute_position_after_trade(100, 10.0, "SELL", -50, 12.0, 1.0)
        
        # Should be equivalent to selling 50 shares
        assert shares == 50
        assert cost == 10.0
        assert abs(pnl - 99.0) < 0.01  # (12-10)*50 - 1
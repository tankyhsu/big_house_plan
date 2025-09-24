"""
聚合服务层 - 提供可复用的数据聚合功能
支持按需获取数据，避免重复调用，提高性能
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from .dashboard_svc import get_dashboard, list_category, list_position, list_signal_all
from .watchlist_svc import list_watchlist
from .txn_svc import list_txn, get_monthly_pnl_stats
from .position_svc import list_positions_raw
from .instrument_svc import list_instruments
from .category_svc import list_categories
from ..db import get_conn

logger = logging.getLogger(__name__)


@dataclass
class DataRequest:
    """数据请求配置"""
    include_dashboard: bool = False
    include_categories: bool = False
    include_positions: bool = False
    include_signals: bool = False
    include_watchlist: bool = False
    include_transactions: bool = False
    include_instruments: bool = False
    include_settings: bool = False
    include_monthly_stats: bool = False

    # 参数配置
    date: Optional[str] = None
    signal_params: Optional[Dict[str, Any]] = None
    txn_params: Optional[Dict[str, Any]] = None
    position_params: Optional[Dict[str, Any]] = None


class DataFetcher:
    """数据获取器基类"""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def get_dashboard_data(self, date: str) -> Dict[str, Any]:
        """获取Dashboard数据"""
        key = f"dashboard_{date}"
        if key not in self._cache:
            self._cache[key] = get_dashboard(date)
        return self._cache[key]

    def get_categories_data(self, date: str) -> List[Dict[str, Any]]:
        """获取分类数据"""
        key = f"categories_{date}"
        if key not in self._cache:
            self._cache[key] = list_category(date)
        return self._cache[key]

    def get_positions_data(self, date: str) -> List[Dict[str, Any]]:
        """获取持仓数据"""
        key = f"positions_{date}"
        if key not in self._cache:
            self._cache[key] = list_position(date)
        return self._cache[key]

    def get_positions_raw_data(self, include_zero: bool = True, with_price: bool = True, date: str = None) -> List[Dict[str, Any]]:
        """获取原始持仓数据"""
        key = f"positions_raw_{include_zero}_{with_price}_{date}"
        if key not in self._cache:
            self._cache[key] = list_positions_raw(include_zero=include_zero, with_price=with_price, on_date_yyyymmdd=date)
        return self._cache[key]

    def get_signals_data(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取信号数据"""
        key = f"signals_{hash(str(sorted(params.items())))}"
        if key not in self._cache:
            self._cache[key] = list_signal_all(**params)
        return self._cache[key]

    def get_watchlist_data(self, date: str = None) -> Dict[str, Any]:
        """获取监控列表数据"""
        key = f"watchlist_{date}"
        if key not in self._cache:
            items = list_watchlist(with_last_price=True, on_date_yyyymmdd=date)
            self._cache[key] = {"items": items}
        return self._cache[key]

    def get_transactions_data(self, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """获取交易数据"""
        key = f"transactions_{page}_{size}"
        if key not in self._cache:
            total, items = list_txn(page, size)
            self._cache[key] = {"total": total, "items": items}
        return self._cache[key]

    def get_instruments_data(self) -> List[Dict[str, Any]]:
        """获取标的列表数据"""
        key = "instruments"
        if key not in self._cache:
            self._cache[key] = list_instruments()
        return self._cache[key]

    def get_categories_list_data(self) -> List[Dict[str, Any]]:
        """获取分类列表数据"""
        key = "categories_list"
        if key not in self._cache:
            self._cache[key] = list_categories()
        return self._cache[key]

    def get_monthly_stats_data(self) -> Dict[str, Any]:
        """获取月度统计数据"""
        key = "monthly_stats"
        if key not in self._cache:
            items = get_monthly_pnl_stats()
            self._cache[key] = {"items": items}
        return self._cache[key]

    def get_latest_trading_date(self) -> str:
        """获取最新交易日期"""
        key = "latest_trading_date"
        if key not in self._cache:
            try:
                with get_conn() as conn:
                    result = conn.execute("""
                        SELECT MAX(trade_date) as latest_date
                        FROM price_eod
                    """).fetchone()

                    if result and result["latest_date"]:
                        self._cache[key] = result["latest_date"]
                    else:
                        # 如果没有价格数据，使用当前日期
                        from datetime import datetime
                        self._cache[key] = datetime.now().strftime("%Y-%m-%d")
            except Exception:
                # 出错时使用当前日期
                from datetime import datetime
                self._cache[key] = datetime.now().strftime("%Y-%m-%d")
        return self._cache[key]


class AggregatorService:
    """聚合服务 - 协调各种数据获取"""

    def __init__(self):
        self.fetcher = DataFetcher()

    def fetch_data(self, request: DataRequest) -> Dict[str, Any]:
        """根据请求配置获取数据"""
        result = {}

        # 确保有日期
        if not request.date:
            request.date = self.fetcher.get_latest_trading_date().replace("-", "")

        # 根据配置获取数据
        if request.include_dashboard:
            result["dashboard"] = self.fetcher.get_dashboard_data(request.date)

        if request.include_categories:
            result["categories"] = self.fetcher.get_categories_data(request.date)

        if request.include_positions:
            if request.position_params:
                result["positions"] = self.fetcher.get_positions_raw_data(**request.position_params)
            else:
                result["positions"] = self.fetcher.get_positions_data(request.date)

        if request.include_signals:
            params = request.signal_params or {}
            result["signals"] = self.fetcher.get_signals_data(params)

        if request.include_watchlist:
            result["watchlist"] = self.fetcher.get_watchlist_data(request.date)

        if request.include_transactions:
            params = request.txn_params or {"page": 1, "size": 20}
            result["transactions"] = self.fetcher.get_transactions_data(**params)

        if request.include_instruments:
            result["instruments"] = self.fetcher.get_instruments_data()

        if request.include_settings:
            # 这里可以后续添加设置相关的数据获取
            from .config_svc import get_config
            result["settings"] = get_config()

        if request.include_monthly_stats:
            result["monthly_stats"] = self.fetcher.get_monthly_stats_data()

        # 添加元数据
        result["_meta"] = {
            "date": request.date,
            "latest_trading_date": self.fetcher.get_latest_trading_date(),
            "data_keys": list(result.keys())
        }

        return result

    def fetch_dashboard_full(self, date: str = None) -> Dict[str, Any]:
        """获取Dashboard页面完整数据"""
        request = DataRequest(
            include_dashboard=True,
            include_categories=True,
            include_positions=True,
            include_signals=True,
            date=date,
            signal_params={
                "start_date": self._get_signal_start_date(date),
                "end_date": self._format_date(date),
                "limit": 1000
            }
        )
        return self.fetch_data(request)

    def fetch_watchlist_full(self, date: str = None) -> Dict[str, Any]:
        """获取Watchlist页面完整数据"""
        # 首先获取监控列表
        watchlist_data = self.fetcher.get_watchlist_data(date)

        # 批量获取每个标的的信号数据
        signals_batch = self._fetch_signals_batch(
            watchlist_data.get("items", []),
            date
        )

        request = DataRequest(
            include_watchlist=True,
            include_instruments=True,
            date=date
        )
        result = self.fetch_data(request)
        result["signals_batch"] = signals_batch

        return result

    def fetch_transaction_page(self, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """获取Transaction页面完整数据"""
        request = DataRequest(
            include_transactions=True,
            include_monthly_stats=True,
            include_instruments=True,
            include_settings=True,
            txn_params={"page": page, "size": size},
            position_params={"include_zero": True, "with_price": True}
        )
        result = self.fetch_data(request)
        result["categories_list"] = self.fetcher.get_categories_list_data()
        result["positions_raw"] = self.fetcher.get_positions_raw_data(include_zero=True, with_price=True)

        return result

    def _get_signal_start_date(self, end_date: str = None) -> str:
        """获取信号查询的开始日期（一个月前）"""
        from datetime import datetime, timedelta

        if end_date:
            date_obj = datetime.strptime(end_date, "%Y%m%d")
        else:
            date_obj = datetime.now()

        start_date = date_obj - timedelta(days=30)
        return start_date.strftime("%Y-%m-%d")

    def _format_date(self, date: str = None) -> str:
        """格式化日期为YYYY-MM-DD"""
        if not date:
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d")

        if len(date) == 8:  # YYYYMMDD
            return f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        return date

    def _fetch_signals_batch(self, watchlist_items: List[Dict], date: str = None) -> Dict[str, List]:
        """批量获取监控标的的信号数据"""
        if not watchlist_items:
            return {}

        signals_batch = {}
        end_date = self._format_date(date)
        start_date = self._get_signal_start_date(date)

        # 批量获取所有标的的信号数据
        ts_codes = [item.get("ts_code") for item in watchlist_items if item.get("ts_code")]

        # 这里可以优化为一次查询获取所有信号，然后按ts_code分组
        for ts_code in ts_codes:
            try:
                signals = self.fetcher.get_signals_data({
                    "ts_code": ts_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": 3
                })
                signals_batch[ts_code] = signals
            except Exception as e:
                logger.warning(f"Failed to fetch signals for {ts_code}: {e}")
                signals_batch[ts_code] = []

        return signals_batch


# 全局实例
aggregator_service = AggregatorService()
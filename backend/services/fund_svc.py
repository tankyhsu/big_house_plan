from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Optional
from ..providers.tushare_provider import TuShareProvider
from .config_svc import get_config


# Simple in-memory cache for fund profiles with TTL
_fund_profile_cache: dict[str, tuple[dict, datetime]] = {}
_cache_ttl_hours = 4  # Cache for 4 hours


def _get_recent_quarters(months_back: int = 18) -> list[str]:
    """Get the last few quarter end dates for fund disclosure periods."""
    from datetime import date

    today = date.today()
    quarters = []

    # Get quarter end dates (Mar 31, Jun 30, Sep 30, Dec 31)
    for i in range(months_back // 3 + 2):  # Get a few extra quarters
        year = today.year
        month = today.month

        # Move back i quarters
        month -= i * 3
        while month <= 0:
            month += 12
            year -= 1

        # Find quarter end for this period
        if month <= 3:
            quarter_end = f"{year}0331"
        elif month <= 6:
            quarter_end = f"{year}0630"
        elif month <= 9:
            quarter_end = f"{year}0930"
        else:
            quarter_end = f"{year}1231"

        if quarter_end not in quarters:
            quarters.append(quarter_end)

    return sorted(quarters, reverse=True)[:6]  # Return last 6 quarters


def _calculate_portfolio_changes(current_df, previous_df):
    """Calculate weight and position changes between two portfolio periods."""
    changes = []

    if current_df is None or current_df.empty:
        return changes

    # Convert previous holdings to dict for lookup
    prev_holdings = {}
    if previous_df is not None and not previous_df.empty:
        for _, row in previous_df.iterrows():
            stock_code = row.get('stock_code', '')
            prev_holdings[stock_code] = {
                'weight': float(row.get('weight', 0) or 0),
                'mkv': float(row.get('mkv', 0) or 0),
                'amount': float(row.get('amount', 0) or 0)
            }

    # Process current holdings and calculate changes
    for _, row in current_df.iterrows():
        stock_code = row.get('stock_code', '')
        stock_name = row.get('stock_name', '')
        current_weight = float(row.get('weight', 0) or 0)
        current_mkv = float(row.get('mkv', 0) or 0)
        current_amount = float(row.get('amount', 0) or 0)

        prev_data = prev_holdings.get(stock_code, {'weight': 0, 'mkv': 0, 'amount': 0})
        prev_weight = prev_data['weight']
        prev_mkv = prev_data['mkv']

        changes.append({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'current_weight': current_weight,
            'previous_weight': prev_weight,
            'weight_change': current_weight - prev_weight,
            'current_mkv': current_mkv,
            'previous_mkv': prev_mkv,
            'mkv_change': current_mkv - prev_mkv,
            'current_amount': current_amount,
            'is_new': prev_weight == 0,
            'is_increased': current_weight > prev_weight,
            'is_reduced': current_weight < prev_weight
        })

    # Sort by current weight descending
    changes.sort(key=lambda x: x['current_weight'], reverse=True)
    return changes


def fetch_fund_profile(ts_code: str) -> dict[str, Any]:
    """
    Fetch comprehensive fund profile including holdings, scale, and managers.

    Args:
        ts_code: Fund code (e.g., '000001.OF')

    Returns:
        dict with keys: holdings, scale, managers
        - holdings: dict with portfolio changes between last 2 disclosure periods
        - scale: dict with recent fund share/NAV data for scale calculation
        - managers: list of current fund manager info
    """
    # Check cache first
    now = datetime.now()
    if ts_code in _fund_profile_cache:
        cached_data, cached_time = _fund_profile_cache[ts_code]
        if now - cached_time < timedelta(hours=_cache_ttl_hours):
            return cached_data

    cfg = get_config()
    token = cfg.get("tushare_token")

    if not token:
        # Return empty structure if no token
        result = {
            "holdings": {"error": "no_token", "current": [], "previous": [], "changes": []},
            "scale": {"error": "no_token", "recent_shares": [], "nav_data": []},
            "managers": {"error": "no_token", "current_managers": []}
        }
        return result

    # Initialize TuShare provider
    fund_rate_per_min = None
    try:
        v = int(cfg.get("tushare_fund_rate_per_min", 0) or 0)
        fund_rate_per_min = v if v > 0 else None
    except Exception:
        fund_rate_per_min = None

    provider = TuShareProvider(token, fund_rate_per_min)

    # Fetch data
    quarters = _get_recent_quarters()
    holdings_data = {"current": [], "previous": [], "changes": [], "error": None}
    scale_data = {"recent_shares": [], "nav_data": [], "error": None}
    manager_data = {"current_managers": [], "error": None}

    try:
        # 1. Get fund portfolio holdings for last 2 quarters
        current_portfolio = None
        previous_portfolio = None

        for i, quarter_date in enumerate(quarters[:4]):  # Try last 4 quarters
            try:
                # Get portfolio for this quarter (try ±15 days around quarter end)
                start_date = (datetime.strptime(quarter_date, '%Y%m%d') - timedelta(days=15)).strftime('%Y%m%d')
                end_date = (datetime.strptime(quarter_date, '%Y%m%d') + timedelta(days=15)).strftime('%Y%m%d')

                portfolio_df = provider.fund_portfolio_window(ts_code, start_date, end_date)

                if portfolio_df is not None and not portfolio_df.empty:
                    if current_portfolio is None:
                        current_portfolio = portfolio_df
                        holdings_data["current"] = portfolio_df.to_dict('records')
                    elif previous_portfolio is None:
                        previous_portfolio = portfolio_df
                        holdings_data["previous"] = portfolio_df.to_dict('records')
                        break

            except Exception as e:
                print(f"[fund_svc] error fetching portfolio for {quarter_date}: {e}")
                continue

        # Calculate portfolio changes
        if current_portfolio is not None:
            holdings_data["changes"] = _calculate_portfolio_changes(current_portfolio, previous_portfolio)

    except Exception as e:
        holdings_data["error"] = str(e)
        print(f"[fund_svc] holdings error: {e}")

    try:
        # 2. Get fund share data for scale calculation
        # Get last 90 days of share data
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

        share_df = provider.fund_share_window(ts_code, start_date, end_date)
        if share_df is not None and not share_df.empty:
            # Get most recent 10 records
            recent_shares = share_df.tail(10).to_dict('records')
            scale_data["recent_shares"] = recent_shares

        # Also get NAV data for scale calculation
        nav_df = provider.fund_nav_window(ts_code, start_date, end_date)
        if nav_df is not None and not nav_df.empty:
            recent_nav = nav_df.tail(10).to_dict('records')
            scale_data["nav_data"] = recent_nav

    except Exception as e:
        scale_data["error"] = str(e)
        print(f"[fund_svc] scale error: {e}")

    try:
        # 3. Get fund manager data
        manager_df = provider.fund_manager(ts_code)
        if manager_df is not None and not manager_df.empty:
            # Filter for current managers (end_date is null or future)
            current_managers = []
            for _, row in manager_df.iterrows():
                end_date = row.get('end_date')
                if not end_date or end_date == '' or end_date is None:
                    # Current manager
                    current_managers.append({
                        'name': row.get('name', ''),
                        'gender': row.get('gender', ''),
                        'education': row.get('education', ''),
                        'nationality': row.get('nationality', ''),
                        'begin_date': row.get('begin_date', ''),
                        'end_date': row.get('end_date', ''),
                        'resume': row.get('resume', '')
                    })
                else:
                    # Check if end_date is in the future
                    try:
                        end_dt = datetime.strptime(str(end_date), '%Y%m%d')
                        if end_dt > datetime.now():
                            current_managers.append({
                                'name': row.get('name', ''),
                                'gender': row.get('gender', ''),
                                'education': row.get('education', ''),
                                'nationality': row.get('nationality', ''),
                                'begin_date': row.get('begin_date', ''),
                                'end_date': row.get('end_date', ''),
                                'resume': row.get('resume', '')
                            })
                    except Exception:
                        # If can't parse date, assume current
                        current_managers.append({
                            'name': row.get('name', ''),
                            'gender': row.get('gender', ''),
                            'education': row.get('education', ''),
                            'nationality': row.get('nationality', ''),
                            'begin_date': row.get('begin_date', ''),
                            'end_date': row.get('end_date', ''),
                            'resume': row.get('resume', '')
                        })

            manager_data["current_managers"] = current_managers

    except Exception as e:
        manager_data["error"] = str(e)
        print(f"[fund_svc] manager error: {e}")

    # Prepare final result
    result = {
        "holdings": holdings_data,
        "scale": scale_data,
        "managers": manager_data
    }

    # Cache the result
    _fund_profile_cache[ts_code] = (result, now)

    return result


def clear_fund_profile_cache():
    """Clear the fund profile cache."""
    global _fund_profile_cache
    _fund_profile_cache.clear()
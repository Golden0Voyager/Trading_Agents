import logging
from typing import Annotated

logger = logging.getLogger(__name__)

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .akshare_vendor import (
    get_stock_data as get_akshare_stock_data,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_indicators as get_akshare_indicators,
    get_news as get_akshare_news,
    get_insider_transactions as get_akshare_insider_transactions,
    get_company_announcements as get_akshare_company_announcements,
    get_fund_flow as get_akshare_fund_flow,
    get_northbound_hold as get_akshare_northbound_hold,
    get_restricted_release as get_akshare_restricted_release,
    get_industry_valuation as get_akshare_industry_valuation,
    get_macro_indicators as get_akshare_macro_indicators,
    get_earnings_estimates as get_akshare_earnings_estimates,
    get_institutional_holdings as get_akshare_institutional_holdings,
)
from .akshare_common import is_a_share_ticker

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators",
            "get_fund_flow",
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_industry_valuation",
            "get_earnings_estimates",
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
            "get_restricted_release",
            "get_institutional_holdings",
            "get_northbound_hold",
            "get_macro_indicators",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicators,
    },
    "get_fund_flow": {
        "akshare": get_akshare_fund_flow,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "akshare": get_akshare_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "akshare": get_akshare_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "akshare": get_akshare_income_statement,
    },
    "get_industry_valuation": {
        "akshare": get_akshare_industry_valuation,
    },
    "get_earnings_estimates": {
        "akshare": get_akshare_earnings_estimates,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "akshare": get_akshare_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "akshare": get_akshare_insider_transactions,
    },
    "get_company_announcements": {
        "akshare": get_akshare_company_announcements,
    },
    "get_restricted_release": {
        "akshare": get_akshare_restricted_release,
    },
    "get_institutional_holdings": {
        "akshare": get_akshare_institutional_holdings,
    },
    "get_northbound_hold": {
        "akshare": get_akshare_northbound_hold,
    },
    "get_macro_indicators": {
        "akshare": get_akshare_macro_indicators,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # A-share routing: if the first positional arg looks like an A-share ticker,
    # hoist akshare to the front of the fallback chain. yfinance still serves as
    # ultimate backup if akshare fails with AlphaVantageRateLimitError.
    symbol = args[0] if args else kwargs.get("symbol") or kwargs.get("ticker")
    if (
        isinstance(symbol, str)
        and is_a_share_ticker(symbol)
        and "akshare" in VENDOR_METHODS[method]
    ):
        primary_vendors = ["akshare"] + [v for v in primary_vendors if v != "akshare"]

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except Exception as exc:
            logger.debug(
                "Vendor '%s' failed for method='%s' symbol='%s': %s(%s)",
                vendor,
                method,
                args[0] if args else kwargs.get("symbol") or kwargs.get("ticker"),
                type(exc).__name__,
                exc,
            )
            continue  # Try next vendor in fallback chain

    logger.error("No available vendor for method='%s' symbol='%s'", method, args[0] if args else kwargs.get("symbol") or kwargs.get("ticker"))
    raise RuntimeError(f"No available vendor for '{method}'")
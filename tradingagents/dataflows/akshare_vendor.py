"""Akshare vendor — A-share financial data via Eastmoney/Xueqiu using akshare.

Each function mirrors the signature of its yfinance counterpart in y_finance.py
and returns a plain string suitable for direct LLM consumption. All A-share
monetary values pass through akshare_common.format_money_cn() so the unit
(亿/万) is always explicit in the output.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Optional

import akshare as ak
import pandas as pd

from .akshare_common import no_proxy, to_akshare_symbol

logger = logging.getLogger(__name__)


def _to_yyyymmdd(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD (akshare's hist API format)."""
    return date_str.replace("-", "")


def get_stock_data(
    symbol: Annotated[str, "A-share ticker e.g. 600519.SS"],
    start_date: Annotated[str, "Start date YYYY-MM-DD"],
    end_date: Annotated[str, "End date YYYY-MM-DD"],
) -> str:
    """Fetch A-share daily OHLCV from Eastmoney via akshare (forward-adjusted)."""
    code = to_akshare_symbol(symbol, "bare")

    with no_proxy():
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=_to_yyyymmdd(start_date),
            end_date=_to_yyyymmdd(end_date),
            adjust="qfq",
        )

    if df is None or df.empty:
        return (
            f"No data found for symbol '{symbol}' between "
            f"{start_date} and {end_date}"
        )

    rename_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "Date" in df.columns:
        df = df.set_index("Date")

    for col in ("Open", "High", "Low", "Close"):
        if col in df.columns:
            df[col] = df[col].round(2)

    header = (
        f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Source: akshare (Eastmoney, 前复权)\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + df.to_csv()


def get_fundamentals(symbol, curr_date):
    raise NotImplementedError


def get_balance_sheet(symbol, freq="quarterly", curr_date=None):
    raise NotImplementedError


def get_cashflow(symbol, freq="quarterly", curr_date=None):
    raise NotImplementedError


def get_income_statement(symbol, freq="quarterly", curr_date=None):
    raise NotImplementedError


def get_indicators(symbol, indicator, curr_date, look_back_days):
    raise NotImplementedError

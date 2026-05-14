"""Akshare vendor — A-share financial data via Eastmoney/Xueqiu using akshare.

Each function mirrors the signature of its yfinance counterpart in y_finance.py
and returns a plain string suitable for direct LLM consumption. Implementations
are filled in incrementally; placeholders raise NotImplementedError.
"""
from __future__ import annotations


def get_stock_data(symbol, start_date, end_date):
    raise NotImplementedError


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

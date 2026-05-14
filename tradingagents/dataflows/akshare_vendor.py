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

from .akshare_common import format_money_cn, no_proxy, safe_float, to_akshare_symbol

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


def _safe_call(func, *args, **kwargs):
    """Invoke an akshare function, returning None on any exception."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.debug("akshare call %s failed: %s", getattr(func, "__name__", "?"), exc)
        return None


def _yjbb_report_date_for(curr_date: Optional[str]) -> str:
    """Pick the most recently available yjbb report date as YYYYMMDD.

    Q1 results land in late April, Q2 in late August, Q3 in late October,
    so we lag by ~one month relative to the period-end.
    """
    if curr_date:
        y, m, _ = curr_date.split("-")
        y, m = int(y), int(m)
    else:
        now = datetime.now()
        y, m = now.year, now.month
    if m >= 11:
        return f"{y}0930"
    if m >= 8:
        return f"{y}0630"
    if m >= 5:
        return f"{y}0331"
    return f"{y - 1}0930"


def get_fundamentals(
    symbol: Annotated[str, "A-share ticker"],
    curr_date: Annotated[str, "Current date YYYY-MM-DD"],
) -> str:
    """Combine company-info + latest performance report into a fundamentals brief."""
    bare = to_akshare_symbol(symbol, "bare")

    with no_proxy():
        info_df = _safe_call(ak.stock_individual_info_em, symbol=bare)
        report_date = _yjbb_report_date_for(curr_date)
        yjbb_df = _safe_call(ak.stock_yjbb_em, date=report_date)

    lines = [
        f"# Fundamentals for {symbol.upper()} as of {curr_date}",
        f"# Source: akshare (Eastmoney)",
        "",
    ]

    if info_df is not None and not info_df.empty:
        info = dict(zip(info_df["item"], info_df["value"]))
        for label in ("股票简称", "行业", "上市时间", "总股本", "流通股", "总市值", "流通市值"):
            if label in info and info[label] not in (None, ""):
                v = info[label]
                if label in ("总市值", "流通市值"):
                    v = format_money_cn(safe_float(v))
                elif label in ("总股本", "流通股"):
                    nv = safe_float(v)
                    v = f"{nv:,.0f}" if nv is not None else v
                lines.append(f"- {label}: {v}")
        lines.append("")

    if yjbb_df is not None and not yjbb_df.empty:
        row = yjbb_df[yjbb_df["股票代码"] == bare]
        if not row.empty:
            r = row.iloc[0]
            period = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
            lines.append(f"## 业绩报表 (报告期 {period})")
            for col, label in [
                ("营业总收入-同比增长", "营收同比增长(YoY)"),
                ("净利润-同比增长", "净利润同比增长(YoY)"),
                ("销售毛利率", "毛利率"),
                ("净资产收益率", "ROE"),
                ("每股收益", "EPS"),
                ("每股经营现金流量", "每股经营现金流"),
            ]:
                v = safe_float(r.get(col))
                if v is None:
                    continue
                unit = "%" if any(k in label for k in ("增长", "毛利率", "ROE")) else ""
                lines.append(f"- {label}: {v:.2f}{unit}")

    if len(lines) <= 3:
        return f"No fundamentals available for {symbol} via akshare."
    return "\n".join(lines)


_BALANCE_FIELDS = [
    ("TOTAL_ASSETS", "总资产"),
    ("TOTAL_CURRENT_ASSETS", "流动资产"),
    ("MONETARYFUNDS", "货币资金"),
    ("ACCOUNTS_RECE", "应收账款"),
    ("INVENTORY", "存货"),
    ("FIXED_ASSET", "固定资产"),
    ("TOTAL_LIABILITIES", "总负债"),
    ("TOTAL_CURRENT_LIAB", "流动负债"),
    ("TOTAL_EQUITY", "股东权益合计"),
]


def get_balance_sheet(
    symbol: Annotated[str, "A-share ticker"],
    freq: str = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Fetch A-share balance sheet (latest report period) via akshare."""
    code = to_akshare_symbol(symbol, "upper_prefix")
    with no_proxy():
        df = ak.stock_balance_sheet_by_report_em(symbol=code)

    if df is None or df.empty:
        return f"No balance sheet available for {symbol} via akshare."

    latest = df.iloc[0].to_dict()
    period = latest.get("REPORT_DATE", "N/A")
    header = (
        f"# Balance Sheet for {symbol.upper()} ({period})\n"
        f"# Source: akshare (Eastmoney 资产负债表)\n"
        f"# Currency: CNY (元)\n\n"
    )
    return header + _format_row_section(latest, _BALANCE_FIELDS)


def get_cashflow(
    symbol: Annotated[str, "A-share ticker"],
    freq: str = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Fetch A-share cash flow statement (latest report period) via akshare."""
    code = to_akshare_symbol(symbol, "upper_prefix")
    with no_proxy():
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)

    if df is None or df.empty:
        return f"No cash flow statement available for {symbol} via akshare."

    latest = df.iloc[0].to_dict()
    period = latest.get("REPORT_DATE", "N/A")
    header = (
        f"# Cash Flow Statement for {symbol.upper()} ({period})\n"
        f"# Source: akshare (Eastmoney 现金流量表)\n"
        f"# Currency: CNY (元)\n\n"
    )
    return header + _format_row_section(latest, _CASHFLOW_FIELDS)


_CASHFLOW_FIELDS = [
    ("NETCASH_OPERATE", "经营活动现金流净额"),
    ("NETCASH_INVEST", "投资活动现金流净额"),
    ("NETCASH_FINANCE", "筹资活动现金流净额"),
    ("CCE_ADD", "现金及等价物净增加额"),
    ("END_CCE", "期末现金及等价物余额"),
]


_INCOME_FIELDS = [
    ("TOTAL_OPERATE_INCOME", "营业总收入"),
    ("OPERATE_INCOME", "营业收入"),
    ("OPERATE_COST", "营业成本"),
    ("OPERATE_PROFIT", "营业利润"),
    ("TOTAL_PROFIT", "利润总额"),
    ("PARENT_NETPROFIT", "归母净利润"),
    ("DEDUCT_PARENT_NETPROFIT", "扣非归母净利润"),
    ("BASIC_EPS", "基本每股收益"),
    ("DILUTED_EPS", "稀释每股收益"),
]


def _format_row_section(row: dict, fields) -> str:
    """Format a sequence of (akshare_key, label) pairs from *row* into lines.

    Monetary scale is auto-detected: |v| >= 1000 uses format_money_cn (亿/万);
    smaller values (EPS, ratios) keep raw float with 4 decimal places.
    """
    lines = []
    for key, label in fields:
        v = safe_float(row.get(key))
        if v is None:
            continue
        if abs(v) >= 1000:
            lines.append(f"- {label}: {format_money_cn(v)}")
        else:
            lines.append(f"- {label}: {v:.4f}")
    return "\n".join(lines) if lines else "- (no fields available)"


def get_income_statement(
    symbol: Annotated[str, "A-share ticker"],
    freq: Annotated[str, "annual/quarterly (currently informational)"] = "quarterly",
    curr_date: Optional[str] = None,
) -> str:
    """Fetch A-share income statement (latest report period) via akshare."""
    code = to_akshare_symbol(symbol, "upper_prefix")
    with no_proxy():
        df = ak.stock_profit_sheet_by_report_em(symbol=code)

    if df is None or df.empty:
        return f"No income statement available for {symbol} via akshare."

    latest = df.iloc[0].to_dict()
    period = latest.get("REPORT_DATE", "N/A")

    header = (
        f"# Income Statement for {symbol.upper()} ({period})\n"
        f"# Source: akshare (Eastmoney 利润表)\n"
        f"# Currency: CNY (元)\n\n"
    )
    return header + _format_row_section(latest, _INCOME_FIELDS)


def get_indicators(symbol, indicator, curr_date, look_back_days):
    raise NotImplementedError

"""Real-time snapshot for cross-validating reports against ground truth.

This module is intentionally NOT registered as a vendor — it is consumed
directly by scripts/report_auditor.py to perform fact-checking against
freshly fetched market data.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

import akshare as ak

from .akshare_common import (
    is_a_share_ticker,
    no_proxy,
    safe_float,
    to_akshare_symbol,
)

logger = logging.getLogger(__name__)


def fetch_realtime_snapshot(
    ticker: str, xq_token: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Return a canonical snapshot of current price/PE/PB/market_cap.

    Returns None when *ticker* is not an A-share or every data source fails.
    Xueqiu provides intraday price/PE/PB when XUEQIU_TOKEN is available;
    Eastmoney always provides company name and market cap as a fallback.
    """
    if not is_a_share_ticker(ticker):
        return None

    bare = to_akshare_symbol(ticker, "bare")
    prefixed = to_akshare_symbol(ticker, "upper_prefix")
    token = xq_token or os.getenv("XUEQIU_TOKEN") or os.getenv("XQ_TOKEN")

    snap: dict[str, Any] = {
        "ticker": ticker.upper(),
        "company_name": "",
        "price": None,
        "pe_ttm": None,
        "pb": None,
        "market_cap_yi": None,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": [],
    }

    with no_proxy():
        if token:
            try:
                df = ak.stock_individual_spot_xq(symbol=prefixed, token=token)
                if df is not None and not df.empty:
                    d = dict(zip(df["item"], df["value"]))
                    snap["price"] = safe_float(d.get("最新"))
                    snap["pe_ttm"] = safe_float(d.get("市盈率(TTM)"))
                    snap["pb"] = safe_float(d.get("市净率"))
                    mc = safe_float(d.get("总市值"))
                    if mc is not None:
                        snap["market_cap_yi"] = round(mc / 1e8, 2)
                    snap["sources"].append("xueqiu")
            except Exception as exc:
                logger.debug("xueqiu snapshot failed for %s: %s", ticker, exc)

        try:
            info = ak.stock_individual_info_em(symbol=bare)
            if info is not None and not info.empty:
                d = dict(zip(info["item"], info["value"]))
                snap["company_name"] = str(d.get("股票简称", "")).strip()
                if snap["market_cap_yi"] is None:
                    mc = safe_float(d.get("总市值"))
                    if mc is not None:
                        snap["market_cap_yi"] = round(mc / 1e8, 2)
                snap["sources"].append("eastmoney_info")
        except Exception as exc:
            logger.debug("eastmoney info failed for %s: %s", ticker, exc)

    if not snap["sources"]:
        return None
    return snap

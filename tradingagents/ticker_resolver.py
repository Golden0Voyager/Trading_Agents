"""Ticker resolver: normalize user input to exchange-qualified ticker + company name.

Supports:
- Chinese A-share numeric codes (auto-append .SS/.SZ/.BJ)
- Chinese company names (via akshare lookup + local cache)
- Exchange-qualified tickers (pass-through with yfinance validation)
- International tickers (pass-through)
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
_DEFAULT_CACHE_DIR = os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache"))
_NAME_MAP_PATH = os.path.join(_DEFAULT_CACHE_DIR, "a_share_name_map.json")


_CACHE: Optional[Dict[str, str]] = None


def _load_name_cache() -> Dict[str, str]:
    """Load cached Chinese name -> ticker mapping."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if os.path.exists(_NAME_MAP_PATH):
        with open(_NAME_MAP_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
        return _CACHE
    return {}


def _save_name_cache(data: Dict[str, str]) -> None:
    """Save Chinese name -> ticker mapping to disk."""
    global _CACHE
    os.makedirs(_DEFAULT_CACHE_DIR, exist_ok=True)
    with open(_NAME_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _CACHE = data


# ---------------------------------------------------------------------------
# A-share suffix rules
# ---------------------------------------------------------------------------

_A_SHARE_SUFFIX_RULES = [
    # Shanghai
    (("600", "601", "603", "605", "688"), ".SS"),
    # Shenzhen
    (("000", "001", "002", "003", "300"), ".SZ"),
    # Beijing
    (("82", "83", "87", "88", "43", "92"), ".BJ"),
]


def _is_numeric_code(s: str) -> bool:
    return s.isdigit()


def _append_a_share_suffix(code: str) -> str:
    """Append exchange suffix for Chinese A-share numeric codes.

    Raises ValueError if the prefix is not recognised.
    """
    for prefixes, suffix in _A_SHARE_SUFFIX_RULES:
        if any(code.startswith(p) for p in prefixes):
            return code + suffix
    raise ValueError(
        f"无法识别 A 股代码前缀: {code}。"
        "请输入完整的带后缀代码（如 600901.SS）或有效的 6 位数字代码。"
    )


# ---------------------------------------------------------------------------
# Chinese name resolution (akshare)
# ---------------------------------------------------------------------------


def _build_name_map() -> Dict[str, str]:
    """Fetch full A-share name->ticker mapping from akshare."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise ImportError(
            "解析中文股票名称需要 akshare。请执行: uv pip install akshare"
        ) from exc

    df = ak.stock_info_a_code_name()
    # df columns: ["code", "name"]
    mapping = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        code = str(row["code"]).strip()
        if name and code:
            mapping[name] = code
    return mapping


def _resolve_chinese_name(name: str) -> str:
    """Resolve a Chinese company name to its 6-digit numeric code.

    Uses a local JSON cache; refreshes from akshare on cache miss.
    Falls back to fuzzy matching when exact/partial match fails.
    """
    import difflib

    cache = _load_name_cache()

    def _find(name: str, data: dict) -> str | None:
        # Exact match
        if name in data:
            return data[name]
        # Partial match (input is substring of a cached name)
        for full_name, code in data.items():
            if name in full_name:
                return code
        # Reverse partial match (cached name is substring of input)
        for full_name, code in data.items():
            if full_name in name:
                return code
        # Fuzzy match — best ratio > 0.6
        best_match = difflib.get_close_matches(name, data.keys(), n=1, cutoff=0.6)
        if best_match:
            return data[best_match[0]]
        return None

    result = _find(name, cache)
    if result is not None:
        return result

    # Cache miss — rebuild from akshare
    cache = _build_name_map()
    _save_name_cache(cache)

    result = _find(name, cache)
    if result is not None:
        return result

    # Suggest closest names for the error message
    suggestions = difflib.get_close_matches(name, cache.keys(), n=3, cutoff=0.4)
    hint = f" 您是否想输入: {', '.join(suggestions)}?" if suggestions else ""
    raise ValueError(f"未找到中文名称对应的股票代码: {name}。{hint}")


# ---------------------------------------------------------------------------
# yfinance validation / company name fetch
# ---------------------------------------------------------------------------


def _fetch_company_name(ticker: str) -> Optional[str]:
    """Use yfinance to fetch the company's longName.

    Returns None on any error so the caller can fall back gracefully.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_ticker(user_input: str) -> dict[str, str]:
    """Resolve arbitrary user input to a normalised ticker and company name.

    Returns a dict with keys:
        - "ticker": exchange-qualified ticker (e.g. "600901.SS")
        - "company_name": company long name from yfinance, or empty string
    """
    raw = user_input.strip()
    if not raw:
        raise ValueError("股票代码/名称不能为空")

    # 1. Already has a known exchange suffix -> pass through
    if re.search(r"\.(SS|SZ|BJ|HK|TO|L|T|F|AS|BR|MI|ST|PA|SW|TW|VX|SA)$", raw, re.IGNORECASE):
        ticker = raw.upper()
        company_name = _fetch_company_name(ticker) or ""
        return {"ticker": ticker, "company_name": company_name}

    # 2. Pure numeric -> A-share suffix auto-append
    if _is_numeric_code(raw):
        ticker = _append_a_share_suffix(raw).upper()
        company_name = _fetch_company_name(ticker) or ""
        return {"ticker": ticker, "company_name": company_name}

    # 3. Contains Chinese characters -> resolve via akshare
    if re.search(r"[一-鿿]", raw):
        numeric_code = _resolve_chinese_name(raw)
        ticker = _append_a_share_suffix(numeric_code).upper()
        company_name = _fetch_company_name(ticker) or ""
        return {"ticker": ticker, "company_name": company_name}

    # 4. International ticker (e.g. AAPL, TSLA, BNS.TO)
    ticker = raw.upper()
    company_name = _fetch_company_name(ticker) or ""
    return {"ticker": ticker, "company_name": company_name}

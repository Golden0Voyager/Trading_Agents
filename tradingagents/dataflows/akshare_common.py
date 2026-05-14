"""Shared utilities for the akshare vendor.

Provides symbol-format conversion, proxy isolation, unit normalization and
small numeric helpers. The akshare vendor functions in akshare_vendor.py
depend on this module exclusively for cross-cutting concerns.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional


class AShareSymbolError(ValueError):
    """Raised when an A-share ticker cannot be converted to akshare format."""


_SUFFIX_TO_PREFIX = {".SS": "SH", ".SZ": "SZ", ".BJ": "BJ"}


def is_a_share_ticker(ticker: str) -> bool:
    """Return True iff *ticker* ends with .SS, .SZ or .BJ (case-insensitive)."""
    if not isinstance(ticker, str) or not ticker:
        return False
    return ticker.upper().endswith((".SS", ".SZ", ".BJ"))


def to_akshare_symbol(ticker: str, style: str) -> str:
    """Convert an exchange-qualified ticker to the format akshare expects.

    style:
        "bare"          -> "600519"
        "upper_prefix"  -> "SH600519"
        "lower_prefix"  -> "sh600519"
    """
    if not is_a_share_ticker(ticker):
        raise AShareSymbolError(f"Not an A-share ticker: {ticker!r}")

    upper = ticker.upper()
    code, suffix = upper.split(".")
    prefix = _SUFFIX_TO_PREFIX[f".{suffix}"]

    if style == "bare":
        return code
    if style == "upper_prefix":
        return f"{prefix}{code}"
    if style == "lower_prefix":
        return f"{prefix.lower()}{code}"
    raise ValueError(f"Unknown style: {style!r}")


@contextmanager
def no_proxy() -> Generator[None, None, None]:
    """Temporarily strip proxy env vars so domestic APIs are reached directly."""
    keys = (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    )
    saved = {k: os.environ[k] for k in keys if k in os.environ}
    for k in saved:
        del os.environ[k]
    try:
        yield
    finally:
        for k, v in saved.items():
            os.environ[k] = v

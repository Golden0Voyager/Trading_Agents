"""End-to-end smoke test for the akshare vendor.

Usage:
    uv run python scripts/smoke_akshare.py [TICKER]

Default ticker: 600519.SS (贵州茅台). Each akshare-backed vendor function is
called against the real network; the realtime snapshot is also fetched.
A non-zero exit code indicates one or more checks failed.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta


def main(ticker: str = "600519.SS") -> int:
    from tradingagents.dataflows.akshare_realtime import fetch_realtime_snapshot
    from tradingagents.dataflows.akshare_vendor import (
        get_balance_sheet,
        get_cashflow,
        get_fundamentals,
        get_income_statement,
        get_indicators,
        get_stock_data,
    )

    today = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    checks: list[tuple[str, bool]] = []

    def run(name, fn, *args):
        print(f"\n=== {name} ===")
        try:
            out = fn(*args)
            print(out[:600] + ("..." if len(out) > 600 else ""))
            checks.append((name, True))
        except Exception as exc:
            print(f"FAIL: {exc!r}")
            checks.append((name, False))

    run("stock_data",       get_stock_data,       ticker, start, today)
    run("fundamentals",     get_fundamentals,     ticker, today)
    run("balance_sheet",    get_balance_sheet,    ticker)
    run("cashflow",         get_cashflow,         ticker)
    run("income_statement", get_income_statement, ticker)
    run("indicators(rsi)",  get_indicators,       ticker, "rsi_14", today, 10)

    print("\n=== realtime_snapshot ===")
    snap = fetch_realtime_snapshot(ticker)
    print(snap)
    checks.append(("realtime_snapshot", snap is not None))

    print("\n=== Summary ===")
    for name, ok in checks:
        print(f"  {'✅' if ok else '❌'} {name}")

    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "600519.SS"))

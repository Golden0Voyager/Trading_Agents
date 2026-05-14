from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestRouteToVendor:
    def test_a_share_prefers_akshare(self):
        """A-share tickers (.SS/.SZ/.BJ) should be served by akshare first."""
        from tradingagents.dataflows import interface

        fake_ak = MagicMock(return_value="AKSHARE_RESULT")
        fake_yf = MagicMock(return_value="YFINANCE_RESULT")
        with patch.dict(
            interface.VENDOR_METHODS["get_fundamentals"],
            {"akshare": fake_ak, "yfinance": fake_yf},
            clear=False,
        ):
            result = interface.route_to_vendor(
                "get_fundamentals", "600519.SS", "2026-05-14"
            )
        assert result == "AKSHARE_RESULT"
        fake_ak.assert_called_once_with("600519.SS", "2026-05-14")
        fake_yf.assert_not_called()

    def test_us_share_keeps_yfinance(self):
        from tradingagents.dataflows import interface

        fake_ak = MagicMock(return_value="AKSHARE_RESULT")
        fake_yf = MagicMock(return_value="YFINANCE_RESULT")
        with patch.dict(
            interface.VENDOR_METHODS["get_fundamentals"],
            {"akshare": fake_ak, "yfinance": fake_yf},
            clear=False,
        ):
            result = interface.route_to_vendor(
                "get_fundamentals", "AAPL", "2026-05-14"
            )
        assert result == "YFINANCE_RESULT"
        fake_ak.assert_not_called()

    def test_a_share_falls_back_to_yfinance_on_rate_limit(self):
        from tradingagents.dataflows import interface
        from tradingagents.dataflows.alpha_vantage_common import (
            AlphaVantageRateLimitError,
        )

        def ak_raises(*a, **kw):
            raise AlphaVantageRateLimitError("simulated akshare unavailability")

        fake_yf = MagicMock(return_value="YFINANCE_RESULT")
        with patch.dict(
            interface.VENDOR_METHODS["get_fundamentals"],
            {"akshare": ak_raises, "yfinance": fake_yf},
            clear=False,
        ):
            result = interface.route_to_vendor(
                "get_fundamentals", "600519.SS", "2026-05-14"
            )
        assert result == "YFINANCE_RESULT"

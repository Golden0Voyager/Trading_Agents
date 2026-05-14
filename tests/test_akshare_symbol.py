import pytest

from tradingagents.dataflows.akshare_common import (
    AShareSymbolError,
    is_a_share_ticker,
    to_akshare_symbol,
)


@pytest.mark.unit
class TestToAkshareSymbol:
    def test_shanghai_bare(self):
        assert to_akshare_symbol("600519.SS", "bare") == "600519"

    def test_shenzhen_bare(self):
        assert to_akshare_symbol("000001.SZ", "bare") == "000001"

    def test_beijing_bare(self):
        assert to_akshare_symbol("832000.BJ", "bare") == "832000"

    def test_shanghai_upper_prefix(self):
        assert to_akshare_symbol("600519.SS", "upper_prefix") == "SH600519"

    def test_shenzhen_upper_prefix(self):
        assert to_akshare_symbol("000001.SZ", "upper_prefix") == "SZ000001"

    def test_shanghai_lower_prefix(self):
        assert to_akshare_symbol("600519.SS", "lower_prefix") == "sh600519"

    def test_case_insensitive(self):
        assert to_akshare_symbol("600519.ss", "bare") == "600519"

    def test_non_a_share_raises(self):
        with pytest.raises(AShareSymbolError):
            to_akshare_symbol("AAPL", "bare")

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError):
            to_akshare_symbol("600519.SS", "weird")


@pytest.mark.unit
class TestIsAShareTicker:
    @pytest.mark.parametrize("t", ["600519.SS", "000001.SZ", "832000.BJ", "600519.ss"])
    def test_yes(self, t):
        assert is_a_share_ticker(t) is True

    @pytest.mark.parametrize("t", ["AAPL", "9988.HK", "TSM", "", "600519"])
    def test_no(self, t):
        assert is_a_share_ticker(t) is False

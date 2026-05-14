import pytest

from tradingagents.dataflows.akshare_common import (
    format_money_cn,
    safe_float,
    to_yuan,
)


@pytest.mark.unit
class TestToYuan:
    def test_passthrough_yuan(self):
        assert to_yuan(5_540_000_000, "yuan") == 5_540_000_000.0

    def test_from_wan(self):
        assert to_yuan(55_400, "wan") == 554_000_000.0

    def test_from_yi(self):
        assert to_yuan(5.54, "yi") == 554_000_000.0

    def test_none_returns_none(self):
        assert to_yuan(None, "yuan") is None

    def test_nan_returns_none(self):
        assert to_yuan(float("nan"), "yuan") is None

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            to_yuan(100, "dollars")


@pytest.mark.unit
class TestFormatMoneyCN:
    def test_yi_scale(self):
        assert format_money_cn(5_540_000_000) == "55.40亿"

    def test_wan_scale(self):
        assert format_money_cn(1_234_567) == "123.46万"

    def test_below_wan(self):
        assert format_money_cn(5000) == "5000.00"

    def test_none(self):
        assert format_money_cn(None) == "N/A"

    def test_negative_yi(self):
        assert format_money_cn(-5_540_000_000) == "-55.40亿"


@pytest.mark.unit
class TestSafeFloat:
    def test_str(self):
        assert safe_float("12.5") == 12.5

    def test_none(self):
        assert safe_float(None) is None

    def test_nan(self):
        assert safe_float(float("nan")) is None

    def test_bad_str(self):
        assert safe_float("--") is None

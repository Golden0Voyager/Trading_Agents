from unittest.mock import patch

import pandas as pd
import pytest


@pytest.mark.unit
class TestRealtimeSnapshot:
    def test_returns_canonical_dict(self):
        from tradingagents.dataflows.akshare_realtime import fetch_realtime_snapshot

        spot_df = pd.DataFrame({
            "item": ["最新", "总市值", "市盈率(TTM)", "市净率"],
            "value": [1680.5, 2_108_000_000_000.0, 25.3, 8.7],
        })
        info_df = pd.DataFrame({
            "item": ["股票简称", "总市值"],
            "value": ["贵州茅台", 2_108_000_000_000.0],
        })
        with patch("tradingagents.dataflows.akshare_realtime.ak") as mock_ak:
            mock_ak.stock_individual_spot_xq.return_value = spot_df
            mock_ak.stock_individual_info_em.return_value = info_df
            snap = fetch_realtime_snapshot("600519.SS", xq_token="dummy")

        assert snap["ticker"] == "600519.SS"
        assert snap["company_name"] == "贵州茅台"
        assert snap["price"] == pytest.approx(1680.5)
        assert snap["pe_ttm"] == pytest.approx(25.3)
        assert snap["pb"] == pytest.approx(8.7)
        assert snap["market_cap_yi"] == pytest.approx(21080.0, rel=1e-3)

    def test_non_a_share_returns_none(self):
        from tradingagents.dataflows.akshare_realtime import fetch_realtime_snapshot

        assert fetch_realtime_snapshot("AAPL") is None

    def test_works_without_xueqiu_token(self):
        """Falls back to Eastmoney info when no XQ token is supplied."""
        from tradingagents.dataflows.akshare_realtime import fetch_realtime_snapshot

        info_df = pd.DataFrame({
            "item": ["股票简称", "总市值"],
            "value": ["贵州茅台", 2_108_000_000_000.0],
        })
        with patch("tradingagents.dataflows.akshare_realtime.ak") as mock_ak:
            mock_ak.stock_individual_info_em.return_value = info_df
            snap = fetch_realtime_snapshot("600519.SS", xq_token=None)
        assert snap is not None
        assert snap["company_name"] == "贵州茅台"
        assert snap["market_cap_yi"] == pytest.approx(21080.0, rel=1e-3)
        assert snap["price"] is None

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.mark.unit
class TestAkshareStockData:
    def test_basic_ohlcv_returned_as_csv(self):
        from tradingagents.dataflows import akshare_vendor

        fake_df = pd.DataFrame({
            "日期": ["2026-05-10", "2026-05-13", "2026-05-14"],
            "开盘": [1670.0, 1675.5, 1682.0],
            "收盘": [1680.5, 1681.0, 1683.5],
            "最高": [1690.0, 1685.0, 1690.0],
            "最低": [1665.0, 1670.0, 1678.0],
            "成交量": [120000, 135000, 110000],
        })
        with patch("tradingagents.dataflows.akshare_vendor.ak") as mock_ak:
            mock_ak.stock_zh_a_hist.return_value = fake_df
            result = akshare_vendor.get_stock_data(
                "600519.SS", "2026-05-10", "2026-05-14"
            )

        mock_ak.stock_zh_a_hist.assert_called_once()
        call_kwargs = mock_ak.stock_zh_a_hist.call_args.kwargs
        assert call_kwargs["symbol"] == "600519"
        assert call_kwargs["period"] == "daily"
        assert call_kwargs["adjust"] == "qfq"
        assert "Stock data for 600519.SS" in result
        assert "1680.5" in result

    def test_empty_df_returns_no_data_message(self):
        from tradingagents.dataflows import akshare_vendor

        with patch("tradingagents.dataflows.akshare_vendor.ak") as mock_ak:
            mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
            result = akshare_vendor.get_stock_data(
                "600519.SS", "2026-05-10", "2026-05-14"
            )
        assert "No data" in result

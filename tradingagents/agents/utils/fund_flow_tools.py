from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_fund_flow(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """
    Retrieve individual stock fund flow data (main force, super-large, large, medium, small orders).
    Shows capital inflow/outflow trends to identify smart money accumulation or distribution.
    Uses the configured technical_indicators vendor (akshare for A-shares).
    Args:
        ticker (str): Ticker symbol
    Returns:
        str: A formatted report of fund flow data
    """
    return route_to_vendor("get_fund_flow", ticker)


@tool
def get_northbound_hold(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """
    Retrieve northbound (Stock Connect) foreign investor holding data.
    Shows foreign institutional investor positioning in A-shares via HKEX Stock Connect.
    Uses the configured news_data vendor (akshare for A-shares).
    Args:
        ticker (str): Ticker symbol
    Returns:
        str: A formatted report of northbound holdings
    """
    return route_to_vendor("get_northbound_hold", ticker)

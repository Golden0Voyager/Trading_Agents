# A-Share Data Dimension Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate 6 A-share-specific data dimensions into the TradingAgents pipeline via 2 new analyst nodes (Sentiment, Industry) and enhancements to 2 existing nodes (Fundamentals, Governance).

**Architecture:** Add 7 new data fetcher functions to `akshare_vendor.py`, expose them as LangChain tools, create 2 new analyst nodes following existing patterns, and wire everything into the LangGraph pipeline with conditional logic.

**Tech Stack:** Python 3.12, LangGraph, LangChain, akshare, pandas, pytest

---

## File Structure

### New Files
- `tradingagents/agents/utils/sentiment_data_tools.py` - LangChain tools for fund flow and northbound holdings
- `tradingagents/agents/utils/industry_data_tools.py` - LangChain tools for industry classification and macro indicators
- `tradingagents/agents/utils/governance_data_tools.py` - LangChain tools for restricted release and institution holdings
- `tradingagents/agents/analysts/sentiment_analyst.py` - Sentiment Analyst node implementation
- `tradingagents/agents/analysts/industry_analyst.py` - Industry Analyst node implementation

### Modified Files
- `tradingagents/dataflows/akshare_vendor.py` - Add 7 new data fetcher functions
- `tradingagents/dataflows/interface.py` - Add vendor routing for new tools
- `tradingagents/agents/utils/fundamental_data_tools.py` - Add `get_analyst_forecast` tool
- `tradingagents/agents/utils/agent_utils.py` - Import and re-export new tools
- `tradingagents/agents/analysts/fundamentals_analyst.py` - Add `get_analyst_forecast` tool
- `tradingagents/agents/analysts/governance_analyst.py` - Add `get_restricted_release` and `get_institution_holdings` tools
- `tradingagents/agents/__init__.py` - Export new analyst creators
- `cli/models.py` - Add SENTIMENT and INDUSTRY to AnalystType enum
- `tradingagents/graph/setup.py` - Add new analyst nodes to graph setup
- `tradingagents/graph/conditional_logic.py` - Add conditional logic for new nodes
- `tradingagents/graph/trading_graph.py` - Add tool nodes for new analysts

### Test Files
- `tests/test_akshare_vendor_mocked.py` - Add tests for new data fetchers
- `tests/test_sentiment_tools.py` - Test sentiment tool wrappers
- `tests/test_industry_tools.py` - Test industry tool wrappers
- `tests/test_governance_tools.py` - Test governance tool wrappers

---

## Task 1: Add Data Fetchers to akshare_vendor.py

**Files:**
- Modify: `tradingagents/dataflows/akshare_vendor.py`
- Test: `tests/test_akshare_vendor_mocked.py`

**Context:** This file contains all akshare data fetcher functions. Each function takes a symbol (and optionally dates) and returns a formatted string for LLM consumption. Follow the existing pattern: use `_safe_call()` for akshare invocations, handle empty DataFrames gracefully, return informative messages.

- [ ] **Step 1: Write failing test for `get_fund_flow`**

Add to `tests/test_akshare_vendor_mocked.py`:

```python
@pytest.mark.unit
class TestAkshareFundFlow:
    def test_returns_fund_flow_summary(self):
        from tradingagents.dataflows import akshare_vendor
        
        fake_df = pd.DataFrame({
            "日期": ["2025-05-01", "2025-05-02"],
            "主力净流入-净额": [1000000.0, -500000.0],
            "主力净流入-净占比": [5.5, -2.3],
            "小单净流入-净额": [-200000.0, 100000.0],
        })
        
        with patch.object(ak, "stock_individual_fund_flow", return_value=fake_df):
            result = akshare_vendor.get_fund_flow("300454.SZ", "2025-05-15", look_back_days=2)
        
        assert "Fund Flow for 300454.SZ" in result
        assert "主力净流入" in result
        assert "2025-05-01" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_akshare_vendor_mocked.py::TestAkshareFundFlow::test_returns_fund_flow_summary -v`
Expected: FAIL with "AttributeError: module 'tradingagents.dataflows.akshare_vendor' has no attribute 'get_fund_flow'"

- [ ] **Step 3: Implement `get_fund_flow` in akshare_vendor.py**

Add to `tradingagents/dataflows/akshare_vendor.py` before the news section (around line 378):

```python
def get_fund_flow(
    symbol: Annotated[str, "A-share ticker"],
    curr_date: Annotated[str, "Current date YYYY-MM-DD"],
    look_back_days: Annotated[int, "Days of history"] = 30,
) -> str:
    """Fetch individual stock fund flow (主力/散户净流入)."""
    code = to_akshare_symbol(symbol, "bare")
    market = "sh" if code.startswith(("6", "5")) else "sz"
    
    with _akshare_task_context(f"📊 {symbol} 资金流向"), no_proxy():
        df = _safe_call(ak.stock_individual_fund_flow, stock=code, market=market)
    
    if df is None or df.empty:
        return f"No fund flow data for {symbol}."
    
    df = df.head(look_back_days)
    lines = [f"## Fund Flow for {symbol.upper()} (last {len(df)} trading days)\n"]
    for _, row in df.iterrows():
        lines.append(
            f"{row['日期']}: 主力净流入 {row['主力净流入-净额']:,.0f} "
            f"({row['主力净流入-净占比']:.2f}%), "
            f"散户净流入 {row['小单净流入-净额']:,.0f}"
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_akshare_vendor_mocked.py::TestAkshareFundFlow::test_returns_fund_flow_summary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_akshare_vendor_mocked.py tradingagents/dataflows/akshare_vendor.py
git commit -m "feat(dataflows): add get_fund_flow for A-share fund flow data

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 6: Write failing test for `get_northbound_holdings`**

Add to `tests/test_akshare_vendor_mocked.py`:

```python
@pytest.mark.unit
class TestAkshareNorthboundHoldings:
    def test_returns_northbound_summary(self):
        from tradingagents.dataflows import akshare_vendor
        
        fake_df = pd.DataFrame({
            "持股日期": ["2025-05-01", "2025-05-02"],
            "持股数量": [1000000.0, 1100000.0],
            "持股数量占A股百分比": [2.5, 2.7],
            "持股市值": [50000000.0, 55000000.0],
        })
        
        with patch.object(ak, "stock_hsgt_individual_em", return_value=fake_df):
            result = akshare_vendor.get_northbound_holdings("300454.SZ", "2025-05-15", look_back_days=2)
        
        assert "Northbound Holdings for 300454.SZ" in result
        assert "持股" in result
        assert "2025-05-01" in result
```

- [ ] **Step 7: Implement `get_northbound_holdings`**

Add to `tradingagents/dataflows/akshare_vendor.py`:

```python
def get_northbound_holdings(
    symbol: Annotated[str, "A-share ticker"],
    curr_date: Annotated[str, "Current date YYYY-MM-DD"],
    look_back_days: Annotated[int, "Days of history"] = 30,
) -> str:
    """Fetch northbound (陆股通) holdings history."""
    code = to_akshare_symbol(symbol, "bare")
    
    with _akshare_task_context(f"📊 {symbol} 北向资金"), no_proxy():
        df = _safe_call(ak.stock_hsgt_individual_em, symbol=code)
    
    if df is None or df.empty:
        return f"No northbound holdings data for {symbol}."
    
    df = df.head(look_back_days)
    lines = [f"## Northbound Holdings for {symbol.upper()} (last {len(df)} trading days)\n"]
    for _, row in df.iterrows():
        lines.append(
            f"{row['持股日期']}: 持股 {row['持股数量']:,.0f}股 "
            f"({row['持股数量占A股百分比']:.2f}%), "
            f"市值 {row['持股市值']:,.0f}元"
        )
    return "\n".join(lines)
```

- [ ] **Step 8: Run test and commit**

Run: `pytest tests/test_akshare_vendor_mocked.py::TestAkshareNorthboundHoldings -v`
Expected: PASS

```bash
git add tests/test_akshare_vendor_mocked.py tradingagents/dataflows/akshare_vendor.py
git commit -m "feat(dataflows): add get_northbound_holdings for A-share northbound data

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 9: Write failing test for `get_restricted_release`**

Add to `tests/test_akshare_vendor_mocked.py`:

```python
@pytest.mark.unit
class TestAkshareRestrictedRelease:
    def test_returns_restricted_release_summary(self):
        from tradingagents.dataflows import akshare_vendor
        
        fake_df = pd.DataFrame({
            "股票代码": ["300454", "300454"],
            "解禁时间": ["2025-06-01", "2025-07-01"],
            "限售股类型": ["定向增发", "股权激励"],
            "解禁数量": [1000000.0, 500000.0],
            "实际解禁市值": [50000000.0, 25000000.0],
        })
        
        with patch.object(ak, "stock_restricted_release_detail_em", return_value=fake_df):
            result = akshare_vendor.get_restricted_release("300454.SZ", "2025-05-15", look_forward_days=90)
        
        assert "Upcoming Restricted Releases for 300454.SZ" in result
        assert "2025-06-01" in result
        assert "定向增发" in result
```

- [ ] **Step 10: Implement `get_restricted_release`**

Add to `tradingagents/dataflows/akshare_vendor.py`:

```python
def get_restricted_release(
    symbol: Annotated[str, "A-share ticker"],
    curr_date: Annotated[str, "Current date YYYY-MM-DD"],
    look_forward_days: Annotated[int, "Days to look ahead"] = 90,
) -> str:
    """Fetch upcoming restricted share releases."""
    code = to_akshare_symbol(symbol, "bare")
    
    with _akshare_task_context(f"📊 {symbol} 限售解禁"), no_proxy():
        df = _safe_call(ak.stock_restricted_release_detail_em)
    
    if df is None or df.empty:
        return f"No restricted release data for {symbol}."
    
    from datetime import datetime, timedelta
    curr = datetime.strptime(curr_date, "%Y-%m-%d")
    future = curr + timedelta(days=look_forward_days)
    
    df = df[df["股票代码"] == code]
    df["解禁时间"] = pd.to_datetime(df["解禁时间"])
    df = df[(df["解禁时间"] >= curr) & (df["解禁时间"] <= future)]
    
    if df.empty:
        return f"No upcoming restricted releases for {symbol} in next {look_forward_days} days."
    
    lines = [f"## Upcoming Restricted Releases for {symbol.upper()}\n"]
    for _, row in df.iterrows():
        lines.append(
            f"{row['解禁时间'].strftime('%Y-%m-%d')}: {row['限售股类型']} "
            f"数量 {row['解禁数量']:,.0f}股, "
            f"市值 {row['实际解禁市值']:,.0f}元"
        )
    return "\n".join(lines)
```

- [ ] **Step 11: Run test and commit**

Run: `pytest tests/test_akshare_vendor_mocked.py::TestAkshareRestrictedRelease -v`
Expected: PASS

```bash
git add tests/test_akshare_vendor_mocked.py tradingagents/dataflows/akshare_vendor.py
git commit -m "feat(dataflows): add get_restricted_release for A-share restricted shares

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 12: Implement remaining 4 data fetchers with tests**

Repeat the pattern for:
- `get_industry_valuation(symbol)` - Uses `stock_individual_info_em` + `stock_board_industry_name_ths`
- `get_macro_indicators(curr_date)` - Uses `macro_china_cpi` + `macro_china_pmi`
- `get_analyst_forecast(symbol, curr_date)` - Uses `stock_yjyg_em`
- `get_institution_holdings(symbol)` - Uses `stock_main_stock_holder`

Each requires:
1. Failing test in `tests/test_akshare_vendor_mocked.py`
2. Implementation in `tradingagents/dataflows/akshare_vendor.py`
3. Test run to verify PASS
4. Commit

---

## Task 2: Add Vendor Routing in interface.py

**Files:**
- Modify: `tradingagents/dataflows/interface.py`
- Test: `tests/test_interface_routing.py`

**Context:** The `interface.py` file routes tool calls to vendor implementations. New tools need entries in `TOOLS_CATEGORIES` and `VENDOR_METHODS`.

- [ ] **Step 1: Add imports for new data fetchers**

Modify `tradingagents/dataflows/interface.py`:

```python
from .akshare_vendor import (
    # ... existing imports ...
    get_fund_flow as get_akshare_fund_flow,
    get_northbound_holdings as get_akshare_northbound_holdings,
    get_restricted_release as get_akshare_restricted_release,
    get_industry_valuation as get_akshare_industry_valuation,
    get_macro_indicators as get_akshare_macro_indicators,
    get_analyst_forecast as get_akshare_analyst_forecast,
    get_institution_holdings as get_akshare_institution_holdings,
)
```

- [ ] **Step 2: Add tool categories**

Add to `TOOLS_CATEGORIES`:

```python
"sentiment_data": {
    "description": "Market sentiment via fund flow and northbound holdings",
    "tools": ["get_fund_flow", "get_northbound_holdings"]
},
"industry_data": {
    "description": "Industry classification and macro indicators",
    "tools": ["get_industry_valuation", "get_macro_indicators"]
},
"governance_data": {
    "description": "Governance and restricted release data",
    "tools": ["get_restricted_release", "get_institution_holdings"]
},
"forecast_data": {
    "description": "Analyst forecasts and expectations",
    "tools": ["get_analyst_forecast"]
},
```

- [ ] **Step 3: Add vendor methods**

Add to `VENDOR_METHODS`:

```python
"get_fund_flow": {"akshare": get_akshare_fund_flow},
"get_northbound_holdings": {"akshare": get_akshare_northbound_holdings},
"get_restricted_release": {"akshare": get_akshare_restricted_release},
"get_industry_valuation": {"akshare": get_akshare_industry_valuation},
"get_macro_indicators": {"akshare": get_akshare_macro_indicators},
"get_analyst_forecast": {"akshare": get_akshare_analyst_forecast},
"get_institution_holdings": {"akshare": get_akshare_institution_holdings},
```

- [ ] **Step 4: Write test for new routing**

Add to `tests/test_interface_routing.py`:

```python
def test_a_share_fund_flow_routes_to_akshare(self):
    with patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
        "get_fund_flow": {"akshare": MagicMock(return_value="fund flow data")}
    }):
        from tradingagents.dataflows.interface import route_to_vendor
        result = route_to_vendor("get_fund_flow", "300454.SZ", "2025-05-15")
    assert result == "fund flow data"
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_interface_routing.py -v`
Expected: All PASS

```bash
git add tradingagents/dataflows/interface.py tests/test_interface_routing.py
git commit -m "feat(dataflows): add vendor routing for 7 new A-share data tools

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Create Tool Wrappers

**Files:**
- Create: `tradingagents/agents/utils/sentiment_data_tools.py`
- Create: `tradingagents/agents/utils/industry_data_tools.py`
- Create: `tradingagents/agents/utils/governance_data_tools.py`
- Modify: `tradingagents/agents/utils/fundamental_data_tools.py`
- Modify: `tradingagents/agents/utils/agent_utils.py`
- Test: `tests/test_sentiment_tools.py`, `tests/test_industry_tools.py`, `tests/test_governance_tools.py`

**Context:** Tool wrappers are thin LangChain `@tool` decorators around `route_to_vendor()` calls. They provide type annotations and docstrings for the LLM.

- [ ] **Step 1: Create `sentiment_data_tools.py`**

```python
from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_fund_flow(
    ticker: Annotated[str, "Ticker symbol"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 30,
) -> str:
    """Retrieve fund flow data (主力/散户净流入) for a stock."""
    return route_to_vendor("get_fund_flow", ticker, curr_date, look_back_days)

@tool
def get_northbound_holdings(
    ticker: Annotated[str, "Ticker symbol"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 30,
) -> str:
    """Retrieve northbound (陆股通) holdings data for a stock."""
    return route_to_vendor("get_northbound_holdings", ticker, curr_date, look_back_days)
```

- [ ] **Step 2: Create `industry_data_tools.py`**

```python
from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_industry_valuation(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """Retrieve industry classification and concept boards for a stock."""
    return route_to_vendor("get_industry_valuation", ticker)

@tool
def get_macro_indicators(
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
) -> str:
    """Retrieve latest macroeconomic indicators (CPI, PMI)."""
    return route_to_vendor("get_macro_indicators", curr_date)
```

- [ ] **Step 3: Create `governance_data_tools.py`**

```python
from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_restricted_release(
    ticker: Annotated[str, "Ticker symbol"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
) -> str:
    """Retrieve upcoming restricted share release schedule."""
    return route_to_vendor("get_restricted_release", ticker, curr_date)

@tool
def get_institution_holdings(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """Retrieve top 10 shareholders and institution holdings."""
    return route_to_vendor("get_institution_holdings", ticker)
```

- [ ] **Step 4: Add `get_analyst_forecast` to `fundamental_data_tools.py`**

```python
@tool
def get_analyst_forecast(
    ticker: Annotated[str, "Ticker symbol"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
) -> str:
    """Retrieve analyst earnings forecasts and performance pre-announcements."""
    return route_to_vendor("get_analyst_forecast", ticker, curr_date)
```

- [ ] **Step 5: Update `agent_utils.py` imports**

Add to imports:

```python
from .sentiment_data_tools import get_fund_flow, get_northbound_holdings
from .industry_data_tools import get_industry_valuation, get_macro_indicators
from .governance_data_tools import get_restricted_release, get_institution_holdings
from .fundamental_data_tools import get_analyst_forecast
```

- [ ] **Step 6: Write tests for tool wrappers**

Create `tests/test_sentiment_tools.py`:

```python
from unittest.mock import patch, MagicMock
import pytest

@pytest.mark.unit
class TestSentimentTools:
    def test_get_fund_flow_calls_route_to_vendor(self):
        with patch("tradingagents.agents.utils.sentiment_data_tools.route_to_vendor", return_value="data") as mock:
            from tradingagents.agents.utils.sentiment_data_tools import get_fund_flow
            result = get_fund_flow.invoke({"ticker": "300454.SZ", "curr_date": "2025-05-15"})
        assert result == "data"
        mock.assert_called_once_with("get_fund_flow", "300454.SZ", "2025-05-15", 30)
```

- [ ] **Step 7: Run tests and commit**

Run: `pytest tests/test_sentiment_tools.py tests/test_industry_tools.py tests/test_governance_tools.py -v`
Expected: All PASS

```bash
git add tradingagents/agents/utils/sentiment_data_tools.py \
        tradingagents/agents/utils/industry_data_tools.py \
        tradingagents/agents/utils/governance_data_tools.py \
        tradingagents/agents/utils/fundamental_data_tools.py \
        tradingagents/agents/utils/agent_utils.py \
        tests/test_sentiment_tools.py \
        tests/test_industry_tools.py \
        tests/test_governance_tools.py
git commit -m "feat(tools): add LangChain tool wrappers for 7 new A-share data sources

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Create Analyst Nodes

**Files:**
- Create: `tradingagents/agents/analysts/sentiment_analyst.py`
- Create: `tradingagents/agents/analysts/industry_analyst.py`
- Modify: `tradingagents/agents/analysts/fundamentals_analyst.py`
- Modify: `tradingagents/agents/analysts/governance_analyst.py`
- Modify: `tradingagents/agents/__init__.py`

**Context:** Analyst nodes follow a standard pattern: import tools, create system message, build prompt with `ChatPromptTemplate`, bind tools to LLM, invoke chain, return report. Copy from existing analysts.

- [ ] **Step 1: Create `sentiment_analyst.py`**

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_fund_flow,
    get_northbound_holdings,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config


def create_sentiment_analyst(llm):
    def sentiment_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"], state.get("company_name", ""))

        tools = [
            get_fund_flow,
            get_northbound_holdings,
        ]

        system_message = (
            "You are a Market Sentiment Analyst analyzing fund flows and northbound "
            "(陆股通) holdings for A-share stocks. Focus on: "
            "1) 主力净流入/散户净流入 trends and what they signal about smart money vs retail sentiment, "
            "2) 北向资金持仓变化 and foreign institutional confidence, "
            "3) Divergences between price action and fund flows. "
            "Provide specific, actionable insights with supporting data."
            + " Make sure to append a Markdown table at the end of the report to organize key points."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant will help."
                    " If you have the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return sentiment_analyst_node
```

- [ ] **Step 2: Create `industry_analyst.py`**

Follow the same pattern as `sentiment_analyst.py` but with:
- Tools: `get_industry_valuation`, `get_macro_indicators`
- System message about industry classification and macro context
- Report key: `industry_report`

- [ ] **Step 3: Update `fundamentals_analyst.py`**

Add `get_analyst_forecast` to tools list and mention it in system message.

- [ ] **Step 4: Update `governance_analyst.py`**

Add `get_restricted_release` and `get_institution_holdings` to tools list and mention them in system message.

- [ ] **Step 5: Update `tradingagents/agents/__init__.py`**

Add exports:

```python
from tradingagents.agents.analysts.sentiment_analyst import create_sentiment_analyst
from tradingagents.agents.analysts.industry_analyst import create_industry_analyst
```

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/analysts/sentiment_analyst.py \
        tradingagents/agents/analysts/industry_analyst.py \
        tradingagents/agents/analysts/fundamentals_analyst.py \
        tradingagents/agents/analysts/governance_analyst.py \
        tradingagents/agents/__init__.py
git commit -m "feat(analysts): add Sentiment and Industry analysts, enhance Fundamentals and Governance

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Graph Integration

**Files:**
- Modify: `cli/models.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/trading_graph.py`

**Context:** The graph setup wires analyst nodes into the LangGraph pipeline. Each analyst needs: node creation, conditional logic, tool node, and edges.

- [ ] **Step 1: Update `cli/models.py`**

```python
class AnalystType(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"
    GOVERNANCE = "governance"
    SENTIMENT = "sentiment"
    INDUSTRY = "industry"
```

- [ ] **Step 2: Update `tradingagents/graph/setup.py`**

Add imports:

```python
from tradingagents.agents.analysts.sentiment_analyst import create_sentiment_analyst
from tradingagents.agents.analysts.industry_analyst import create_industry_analyst
```

Add to `setup_graph()`:

```python
if "sentiment" in selected_analysts:
    analyst_nodes["sentiment"] = create_sentiment_analyst(self.quick_thinking_llm)
    delete_nodes["sentiment"] = create_msg_delete()
    tool_nodes["sentiment"] = self.tool_nodes["sentiment"]

if "industry" in selected_analysts:
    analyst_nodes["industry"] = create_industry_analyst(self.quick_thinking_llm)
    delete_nodes["industry"] = create_msg_delete()
    tool_nodes["industry"] = self.tool_nodes["industry"]
```

- [ ] **Step 3: Update `tradingagents/graph/conditional_logic.py`**

Add:

```python
def should_continue_sentiment(self, state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools_sentiment"
    return "Msg Clear Sentiment"

def should_continue_industry(self, state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools_industry"
    return "Msg Clear Industry"
```

- [ ] **Step 4: Update `tradingagents/graph/trading_graph.py`**

Add imports:

```python
from tradingagents.agents.utils.agent_utils import (
    # ... existing imports ...
    get_fund_flow,
    get_northbound_holdings,
    get_industry_valuation,
    get_macro_indicators,
    get_restricted_release,
    get_institution_holdings,
    get_analyst_forecast,
)
```

Add to `_create_tool_nodes()`:

```python
"sentiment": ToolNode([get_fund_flow, get_northbound_holdings]),
"industry": ToolNode([get_industry_valuation, get_macro_indicators]),
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_interface_routing.py tests/test_akshare_vendor_mocked.py -v`
Expected: All PASS

```bash
git add cli/models.py tradingagents/graph/setup.py \
        tradingagents/graph/conditional_logic.py \
        tradingagents/graph/trading_graph.py
git commit -m "feat(graph): integrate Sentiment and Industry analysts into pipeline

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Integration Testing

**Files:**
- Create: `tests/test_integration_ashare.py`

- [ ] **Step 1: Write integration test**

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.integration
class TestAShareIntegration:
    def test_sentiment_analyst_runs_with_mocked_data(self):
        """End-to-end test that sentiment analyst can be instantiated and run."""
        from tradingagents.graph.setup import GraphSetup
        from tradingagents.graph.conditional_logic import ConditionalLogic
        from langgraph.prebuilt import ToolNode
        
        # Mock LLM
        mock_llm = MagicMock()
        
        # Mock tool nodes
        tool_nodes = {
            "market": ToolNode([]),
            "sentiment": ToolNode([]),
        }
        
        setup = GraphSetup(mock_llm, mock_llm, tool_nodes, ConditionalLogic())
        workflow = setup.setup_graph(selected_analysts=["market", "sentiment"])
        
        assert workflow is not None
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration_ashare.py -v`
Expected: PASS

- [ ] **Step 3: Run full regression suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS (or existing failures only)

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_ashare.py
git commit -m "test: add integration test for A-share data pipeline

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Documentation Update

**Files:**
- Modify: `docs/akshare_integration.md`

- [ ] **Step 1: Update documentation**

Add section to `docs/akshare_integration.md` documenting:
- New data dimensions available
- How to enable new analysts via CLI
- A-share optimized defaults

- [ ] **Step 2: Commit**

```bash
git add docs/akshare_integration.md
git commit -m "docs: update akshare integration guide with new data dimensions

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Summary

This plan implements 6 A-share data dimensions through:
- 7 new data fetcher functions in `akshare_vendor.py`
- 7 new LangChain tool wrappers
- 2 new analyst nodes (Sentiment, Industry)
- Enhancements to 2 existing nodes (Fundamentals, Governance)
- Full graph integration with conditional logic
- Comprehensive test coverage

**Total estimated time: 9-14 hours**

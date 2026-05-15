# Design Spec: A-Share Data Dimension Integration

## Date: 2026-05-15
## Status: Draft for Review

---

## 1. Overview

Integrate 6 A-share-specific data dimensions into the TradingAgents pipeline to improve analysis quality for Chinese equities. Based on API testing, we have identified reliable akshare APIs and designed an architecture that balances comprehensiveness with pipeline efficiency.

## 2. API Reliability Summary

| Dimension | Reliable APIs | Broken/Unavailable | Coverage |
|-----------|--------------|-------------------|----------|
| 融资融券/资金流向 | `stock_individual_fund_flow()` | Margin detail APIs (connection errors) | Individual stock only |
| 限售解禁 | `stock_restricted_release_detail_em()`, `stock_restricted_release_stockholder_em()` | None | Good |
| 行业估值对比 | `stock_board_industry_name_ths()`, `stock_board_concept_name_ths()` | PE ratio APIs (KeyError) | Board names only, no PE |
| 宏观指标 | `macro_china_cpi()`, `macro_china_pmi()` | None | Good |
| 分析师预期 | `stock_yjyg_em()` | `stock_jgdy_tj_em()`, `stock_profit_forecast_em()` (NoneType) | Limited to performance pre-announcements |
| 机构持仓 | `stock_hsgt_individual_em()`, `stock_main_stock_holder()` | `stock_hsgt_hold_stock_em()`, `stock_gdfx_free_top_10_em()` | Northbound + top 10 shareholders |

## 3. Architecture Decision

**Selected: Option B (Balanced)**
- 2 new analyst nodes: **Sentiment Analyst**, **Industry Analyst**
- 2 enhanced analyst nodes: **Fundamentals Analyst** (+分析师预期), **Governance Analyst** (+限售解禁)
- Institution holdings (机构持仓) split: northbound → Sentiment Analyst, top 10 shareholders → Governance Analyst

### 3.1 Pipeline Flow

```
START → Market Analyst → Sentiment Analyst → Social Analyst → News Analyst
  → Fundamentals Analyst (+分析师预期) → Governance Analyst (+限售解禁)
  → Industry Analyst (行业估值+宏观)
  → Bull Researcher ↔ Bear Researcher → Research Manager → Trader
  → Risk Analysis → Portfolio Manager → END
```

### 3.2 Analyst Responsibilities

| Analyst | Tools | Report Key Points |
|---------|-------|-------------------|
| Market Analyst | `get_stock_data`, `get_indicators` | Technical trends, support/resistance |
| **Sentiment Analyst** | `get_fund_flow`, `get_northbound_holdings` | Fund flow trends, northbound sentiment |
| Social Analyst | `get_news` (social context) | Social media sentiment |
| News Analyst | `get_news`, `get_global_news`, `get_insider_transactions`, `get_company_announcements` | News impact, insider activity |
| Fundamentals Analyst | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_analyst_forecast` | Financial health, earnings forecasts |
| Governance Analyst | `get_company_announcements`, `get_insider_transactions`, `get_news`, `get_restricted_release`, `get_institution_holdings` | Governance risks, restricted releases, major shareholders |
| **Industry Analyst** | `get_industry_valuation`, `get_macro_indicators` | Industry position, macro context |

## 4. Data Layer Design

### 4.1 New Functions in `akshare_vendor.py`

```python
def get_fund_flow(symbol: str, curr_date: str, look_back_days: int = 30) -> str:
    """Fetch individual stock fund flow data (主力净流入, 散户净流入, etc.)."""
    
def get_northbound_holdings(symbol: str, curr_date: str, look_back_days: int = 30) -> str:
    """Fetch northbound (陆股通) holdings history for a stock."""

def get_restricted_release(symbol: str, curr_date: str, look_forward_days: int = 90) -> str:
    """Fetch upcoming restricted share releases for a stock."""

def get_industry_valuation(symbol: str) -> str:
    """Fetch industry classification and concept boards for a stock."""

def get_macro_indicators(curr_date: str) -> str:
    """Fetch latest CPI and PMI macro indicators."""

def get_analyst_forecast(symbol: str, curr_date: str) -> str:
    """Fetch performance forecast/pre-announcement for a stock."""

def get_institution_holdings(symbol: str) -> str:
    """Fetch top 10 shareholders for a stock."""
```

### 4.2 Vendor Routing in `interface.py`

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
```

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

## 5. Tool Layer Design

### 5.1 New Tool Files

**`sentiment_data_tools.py`**:
```python
from langchain_core.tools import tool
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_fund_flow(ticker: str, curr_date: str, look_back_days: int = 30) -> str:
    """Retrieve fund flow data for a stock."""
    return route_to_vendor("get_fund_flow", ticker, curr_date, look_back_days)

@tool
def get_northbound_holdings(ticker: str, curr_date: str, look_back_days: int = 30) -> str:
    """Retrieve northbound (陆股通) holdings data."""
    return route_to_vendor("get_northbound_holdings", ticker, curr_date, look_back_days)
```

**`industry_data_tools.py`**:
```python
from langchain_core.tools import tool
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_industry_valuation(ticker: str) -> str:
    """Retrieve industry classification and valuation context."""
    return route_to_vendor("get_industry_valuation", ticker)

@tool
def get_macro_indicators(curr_date: str) -> str:
    """Retrieve latest macroeconomic indicators (CPI, PMI)."""
    return route_to_vendor("get_macro_indicators", curr_date)
```

### 5.2 Updated Tool Files

**`governance_data_tools.py`** (new):
```python
@tool
def get_restricted_release(ticker: str, curr_date: str) -> str:
    """Retrieve upcoming restricted share release schedule."""
    return route_to_vendor("get_restricted_release", ticker, curr_date)

@tool
def get_institution_holdings(ticker: str) -> str:
    """Retrieve top 10 shareholders and institution holdings."""
    return route_to_vendor("get_institution_holdings", ticker)
```

**`fundamental_data_tools.py`** (add):
```python
@tool
def get_analyst_forecast(ticker: str, curr_date: str) -> str:
    """Retrieve analyst earnings forecasts and performance pre-announcements."""
    return route_to_vendor("get_analyst_forecast", ticker, curr_date)
```

## 6. Analyst Node Design

### 6.1 Sentiment Analyst

```python
def create_sentiment_analyst(llm):
    def sentiment_analyst_node(state):
        tools = [get_fund_flow, get_northbound_holdings]
        system_message = (
            "You are a Market Sentiment Analyst analyzing fund flows and northbound "
            "(陆股通) holdings for A-share stocks. Focus on: "
            "1) 主力净流入/散户净流入 trends and what they signal about smart money vs retail sentiment, "
            "2) 北向资金持仓变化 and foreign institutional confidence, "
            "3) Divergences between price action and fund flows. "
            "Provide specific, actionable insights with supporting data."
        )
        # ... standard node pattern
    return sentiment_analyst_node
```

### 6.2 Industry Analyst

```python
def create_industry_analyst(llm):
    def industry_analyst_node(state):
        tools = [get_industry_valuation, get_macro_indicators]
        system_message = (
            "You are an Industry and Macro Analyst. For the given stock, analyze: "
            "1) Its industry classification and concept themes (概念板块), "
            "2) How current macro conditions (CPI, PMI) affect its sector, "
            "3) Relative positioning within its industry peers. "
            "Provide sector context that helps traders understand the stock's environment."
        )
        # ... standard node pattern
    return industry_analyst_node
```

## 7. Graph Integration

### 7.1 `cli/models.py`

```python
class AnalystType(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"
    GOVERNANCE = "governance"
    SENTIMENT = "sentiment"      # NEW
    INDUSTRY = "industry"        # NEW
```

### 7.2 `graph/setup.py`

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

### 7.3 `graph/conditional_logic.py`

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

### 7.4 `graph/trading_graph.py`

Add to `_create_tool_nodes()`:
```python
"sentiment": ToolNode([get_fund_flow, get_northbound_holdings]),
"industry": ToolNode([get_industry_valuation, get_macro_indicators]),
```

## 8. A-Share Optimized Defaults

### 8.1 Default Analyst Selection

For A-share tickers, recommended default:
```python
A_SHARE_DEFAULT_ANALYSTS = ["market", "sentiment", "fundamentals", "governance", "industry"]
# Excludes: social (no Twitter/X data), news (covered by governance)
```

### 8.2 CLI Integration

Add `--a-share-mode` flag that:
1. Auto-detects A-share tickers
2. Sets default analysts to A-share optimized set
3. Enables akshare routing
4. Skips social/news analysts

## 9. Error Handling Strategy

All new akshare functions must follow the pattern:
1. Wrap akshare calls in `_safe_call()` or try/except
2. Return informative string messages on failure (not exceptions)
3. Log failures at debug level
4. Allow `route_to_vendor` fallback chain to work

## 10. Testing Plan

### 10.1 Unit Tests
- Mock each new akshare function in `test_akshare_vendor_mocked.py`
- Test tool wrappers in new test files

### 10.2 Integration Tests
- End-to-end test with A-share ticker using new analysts
- Verify reports contain expected sections

### 10.3 Regression Tests
- Ensure existing analysts still work without new tools
- Verify non-A-share tickers unaffected

## 11. Implementation Phases

### Phase 1: Data Layer (2-3 hours)
- Add 7 new functions to `akshare_vendor.py`
- Add vendor routing in `interface.py`
- Write unit tests

### Phase 2: Tool Layer (1-2 hours)
- Create `sentiment_data_tools.py`
- Create `industry_data_tools.py`
- Update `fundamental_data_tools.py` and `governance_data_tools.py`

### Phase 3: Analyst Nodes (2-3 hours)
- Create `sentiment_analyst.py`
- Create `industry_analyst.py`
- Update `fundamentals_analyst.py` and `governance_analyst.py`

### Phase 4: Graph Integration (2-3 hours)
- Update `cli/models.py`
- Update `graph/setup.py`
- Update `graph/conditional_logic.py`
- Update `graph/trading_graph.py`

### Phase 5: CLI & Testing (2-3 hours)
- Add CLI flags
- Write integration tests
- Run regression tests

**Total Estimated Time: 9-14 hours**

## 12. Open Questions

1. Should `get_macro_indicators()` be cached since it's market-wide, not stock-specific?
2. Should we add rate limiting for THS APIs (which are slower)?
3. How to handle the 2+ minute runtime of `stock_gdfx_holding_detail_em()`?
4. Should Industry Analyst run before or after Fundamentals Analyst?
5. Do we need a separate `get_sector_fund_flow()` for industry-level fund flows?

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents is a multi-agent LLM financial trading framework built on LangGraph. It simulates a real-world trading firm with specialized agents (analysts, researchers, trader, risk management, portfolio manager) that collaboratively evaluate market conditions and produce trading decisions.

## Common Commands

### Running the CLI
```bash
uv run tradingagents          # Interactive CLI (preferred)
python -m cli.main            # Run directly from source
```

### Testing
```bash
uv run pytest                  # Run all tests
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests (may need API keys)
uv run pytest -m smoke         # Quick sanity checks
uv run pytest tests/test_specific.py  # Single test file
```

### Installation / Dependencies
```bash
uv pip install -e .            # Editable install with deps
uv pip install socksio         # Required if using SOCKS proxy (e.g. Clash)
```

### Diagnostics
```bash
uv run python scripts/smoke_structured_output.py  # Verify structured output against any provider
```

## High-Level Architecture

### Package Layout
- `tradingagents/` — Core framework (graph orchestration, agents, data flows, LLM clients)
- `cli/` — Interactive terminal UI (Rich + Typer + questionary)
- `tests/` — Pytest suite with markers: `unit`, `integration`, `smoke`

### LangGraph Workflow
The trading pipeline is a `StateGraph` compiled in `graph/setup.py`. Execution order:

1. **Analysts** (parallel via sequential node chain with tool loops):
   - Market Analyst (technical indicators + stock data)
   - Social Media Analyst (news sentiment)
   - News Analyst (global news + insider transactions)
   - Fundamentals Analyst (financial statements)
   Each analyst node has a paired `tools_<name>` node and a `Msg Clear` node to manage context window.

2. **Research Team** — Bull Researcher vs Bear Researcher debate (`max_debate_rounds` configurable).

3. **Research Manager** — Synthesizes debate into a structured `ResearchPlan` (rating + rationale + actions).

4. **Trader** — Translates plan into a concrete `TraderProposal` (action + entry/stop/sizing).

5. **Risk Management** — Aggressive / Neutral / Conservative analysts debate (`max_risk_discuss_rounds`).

6. **Portfolio Manager** — Final structured `PortfolioDecision` (5-tier rating: Buy/Overweight/Hold/Underweight/Sell).

### Dual-LLM Design
- `quick_think_llm` — Used by analysts and debaters (parallel, tool-heavy)
- `deep_think_llm` — Used by Research Manager, Trader, Portfolio Manager (serial decision-making)

Configured via `DEFAULT_CONFIG` in `tradingagents/default_config.py`.

### LLM Client Architecture (`tradingagents/llm_clients/`)
- `factory.py` — Lazy-import factory routing providers to client implementations
- `openai_client.py` — OpenAI-compatible providers (OpenAI, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, SenseNova)
  - `NormalizedChatOpenAI` — Handles Responses API content normalization
  - `DeepSeekChatOpenAI` — Handles DeepSeek thinking-mode `reasoning_content` round-trip via sidecar cache keyed by `message.id`
- Provider-specific clients: `anthropic_client.py`, `google_client.py`, `azure_client.py`
- `model_catalog.py` — Per-provider model lists for CLI selection

### Data Flow Routing (`tradingagents/dataflows/`)
- `interface.py` — Vendor routing layer. Tools are categorized (core_stock_apis, technical_indicators, fundamental_data, news_data); each category maps to a vendor (yfinance or alpha_vantage). Falls back on `AlphaVantageRateLimitError`.
- `config.py` — Global config singleton used by routing logic
- Vendor implementations: `y_finance.py`, `yfinance_news.py`, `alpha_vantage*.py`

### Structured Output Layer (`tradingagents/agents/schemas.py`)
Three Pydantic schemas for decision agents:
- `ResearchPlan` — Research Manager output
- `TraderProposal` — Trader output
- `PortfolioDecision` — Portfolio Manager output

`agents/utils/structured.py` provides `bind_structured()` and `invoke_structured_or_freetext()` so agents use native provider structured output when available and gracefully fall back to free-text generation on failure.

### Persistence
- **Checkpoint resume** (opt-in): LangGraph `SqliteSaver` per ticker at `~/.tradingagents/cache/checkpoints/<TICKER>.db`. Resume with `--checkpoint`; clear with `--clear-checkpoints`.
- **Memory log** (always on): Append-only markdown log at `~/.tradingagents/memory/trading_memory.md`. Stores decisions + later resolves them with realised return and alpha vs SPY. Injected into Portfolio Manager prompt as `past_context`.

### A-Share Ticker Support (`tradingagents/ticker_resolver.py`)
`resolve_ticker(user_input)` handles:
- Exchange-qualified tickers (pass-through)
- Pure numeric A-share codes (auto-append `.SS`/`.SZ`/`.BJ` by prefix rules)
- Chinese company names (akshare lookup with fuzzy matching + local JSON cache)
- International tickers (pass-through)

Resolved `company_name` (from yfinance `longName`) is injected into all agent prompts via `build_instrument_context()` to prevent LLM hallucination of Chinese company names.

### Agent State (`tradingagents/agents/utils/agent_states.py`)
The graph carries a single `AgentState` dict with keys including:
- `company_of_interest`, `company_name`, `trade_date`
- `*_report` for each analyst
- `investment_debate_state` / `risk_debate_state` (history + current responses + count)
- `investment_plan`, `trader_investment_plan`, `final_trade_decision`
- `messages` — LangChain message list

### Important Implementation Notes
- `ChatPromptTemplate` strips `additional_kwargs` (including `reasoning_content`). The DeepSeek sidecar cache works around this by keying on `message.id`, which survives template recreation.
- `deepseek-reasoner` does not support `tool_choice`; `DeepSeekChatOpenAI.with_structured_output` raises `NotImplementedError`, and agents fall back to free text.
- All file I/O uses explicit `encoding="utf-8"` for Windows compatibility.
- Environment variables are loaded from `.env` (copied from `.env.example`) and optionally `.env.enterprise`.

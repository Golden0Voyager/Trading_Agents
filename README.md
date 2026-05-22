<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

# Trading-Agents-A-Share: Optimized Multi-Agent LLM Financial Trading Framework for China A-Share Market

[![A-Share Optimized](https://img.shields.io/badge/A--Share-Optimized-10B981?style=for-the-badge&logo=chinanet&logoColor=white)](#-key-a-share--production-enhancements)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-6366F1?style=for-the-badge&logo=chainlink&logoColor=white)](https://github.com/langchain-ai/langgraph)
[![arXiv](https://img.shields.io/badge/arXiv-2412.20138-B31B1B?style=for-the-badge&logo=arxiv)](https://arxiv.org/abs/2412.20138)
[![License](https://img.shields.io/badge/License-MIT-374151?style=for-the-badge)](LICENSE)

`Trading-Agents-A-Share` is a highly optimized, production-grade customized fork of **TradingAgents** (the state-of-the-art multi-agent financial trading framework originally published by Tauric Research on NeurIPS/arXiv). 

This fork is specifically tailored to address the unique market dynamics, data feeds, and local execution challenges of the **China A-Share (沪深京) Stock Market**, making it a robust platform for domestic quantitative AI research.

---

## 🚀 Key A-Share & Production Enhancements
*Below are the core engineering enhancements and optimizations introduced in this fork to adapt the original framework for domestic A-Share trading:*

### 1. 📊 A-Share Institutional Fund Flow Integration (`get_fund_flow` Routing)
* **The Optimization**: Integrated custom routing logic to ingest domestic institutional "Smart Money" (主力资金、北向资金、大单流向) flow feeds.
* **Why it matters**: In the China A-Share market, retail-heavy sentiment and institutional capital tracking are extremely strong price-driving signals. This integration adds a crucial metric to the News/Sentiment Analyst agents.

### 2. ⚡ Actionable Trading Signal Enforcement (Entry/Stop/Size Constraints)
* **The Optimization**: Enforced a strict structured schema in the **Trader Agent**'s decision module, requiring it to emit precise values for **Entry Price (建仓点)**, **Stop-Loss (止损点)**, and **Position Size (仓位比例)** in every proposed trade.
* **Why it matters**: Moves the multi-agent system from abstract, qualitative investment debates ("bullish/bearish") into concrete, actionable, and testable trade execution orders.

### 3. 🛡️ SOE & Local Anti-Hallucination Context Sanitizer
* **The Optimization**: Implemented global company-name context injection and post-execution regex filtering across critical analyst roles (Industry Analyst, Governance Analyst).
* **Why it matters**: LLMs frequently hallucinate complex Chinese State-Owned Enterprise (SOE) titles, stock symbols, and localized acronyms. This sanitizer ensures 100% data sanity before any report is written to disk.

### 4. 🇨🇳 Local LLM Native Validation & Standardized Clients
* **The Optimization**: Hardened validation clients for cost-efficient Chinese domestic LLMs, specifically supporting **Qwen (Alibaba DashScope)**, **GLM (Zhipu)**, and **DeepSeek-R1** endpoints.
* **Why it matters**: Standardizes the routing and parsing rules for domestic reasoning models, enabling high-performance local inference at a fraction of the cost of western APIs.

### 5. ⏳ TUI & Batch Checkpoint Resume
* **The Optimization**: Optimized command-line shell script behaviors to support bulk TUI backtests and robust state recovery through a unified SQLite cache.
* **Why it matters**: Long backtesting sessions over multiple A-share stocks are vulnerable to API failures. This recovery pipeline ensures interrupted tasks resume seamlessly from the last successful step.

---

## 🏛️ TradingAgents Framework Overview

The core architecture mimics the hierarchy of professional asset management firms. Under a unified state machine managed by **LangGraph**, specialized LLM agents debate, critique, and authorize trading decisions:

```
                  ┌────────────────────────┐
                  │   Fundamental Analyst  │
                  └───────────┬────────────┘
                              ▼
┌──────────────┐  ┌────────────────────────┐  ┌──────────────┐
│ Technical    ├─►│    Research Managers   │◄─┤ News & Fund  │
│ Analyst      │  │   (Bull & Bear Debate) │  │ Flow Analyst │
└──────────────┘  └───────────┬────────────┘  └──────────────┘
                              ▼
                  ┌────────────────────────┐
                  │      Trader Agent      │
                  │ (Concrete Price/Size)  │
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │     Risk & Portfolio   │
                  │         Manager        │
                  └────────────────────────┘
```

* **Analyst Team**: Fundamental Analyst (evaluates balance sheets), Technical Analyst (MACD, RSI indicators), News & Fund Flow Analyst (monitors domestic news and主力资金 flow).
* **Research Team**: Bullish and Bearish Research Managers who debate the analysts' outputs to balance upside potential against inherent localized market risks.
* **Trader Agent**: Combines the synthesized reports to formulate trade proposals (Entry, Stop-Loss, and Sizing).
* **Risk & Portfolio Manager**: Executes risk checks against overall portfolio volatility and approves/rejects the final transaction before writing it to the simulated exchange.

---

## ⚡ Installation & CLI

### Installation

Clone the repository:
```bash
git clone https://github.com/Golden0Voyager/Trading-Agents-A-Share.git
cd Trading-Agents-A-Share
```

Create a virtual environment:
```bash
conda create -n tradingagents-env python=3.13
conda activate tradingagents-env
```

Install the package in editable mode:
```bash
pip install -e .
```

### Config Environment Variables

Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```

Support for major domestic and international providers:
```bash
export DASHSCOPE_API_KEY=...       # Qwen (Alibaba DashScope)
export ZHIPU_API_KEY=...           # GLM (Zhipu)
export DEEPSEEK_API_KEY=...        # DeepSeek
export SENSENOVA_API_KEY=...       # SenseNova (DeepSeek-R1)
export OPENAI_API_KEY=...          # OpenAI (GPT-4o)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
```

---

## 📈 CLI Usage & Backtesting

Launch the interactive Terminal User Interface (TUI):
```bash
tradingagents
# Or run directly from source:
python -m cli.main
```

### Batch Mode & Checkpoint Resume

To run high-volume backtests with automated SQLite session persistence:
```bash
# Run with active checkpoint tracking
tradingagents analyze --checkpoint

# Reset cached states before starting
tradingagents analyze --clear-checkpoints
```

Decisions are persistently logged into `~/.tradingagents/memory/trading_memory.md`, which the Portfolio Manager automatically reviews on subsequent runs for historical reflection.

---

## 🤝 Contribution & License
This project is open-source under the [MIT License](LICENSE).
We welcome contributions to further enhance A-Share localizations (e.g., adding local technical indicators, refining DeepSeek reasoning prompts, or writing new data ingestion connectors).

---

## 📄 Academic Citation
If you find this framework useful in your financial AI or quantitative research, please cite the original foundational work:

```bibtex
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```

import time
from pathlib import Path
from typing import Optional

from cli.batch_dashboard import BatchDashboard, create_batch_layout, update_batch_display
from cli.stats_handler import StatsCallbackHandler
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from rich.live import Live


class BatchRunner:
    """Orchestrates unattended multi-stock analysis."""

    def __init__(
        self,
        tickers: list[str],
        profile_config: dict,
        output_dir: Path,
        checkpoint: bool = False,
    ):
        self.tickers = tickers
        self.profile_config = profile_config
        self.output_dir = Path(output_dir)
        self.checkpoint = checkpoint
        self.completed_tickers: set[str] = set()
        self.failures: dict[str, str] = {}
        self.summaries: dict[str, dict] = {}
        self.dashboard = BatchDashboard(total=len(tickers), profile_name=profile_config.get("name", "default"))

    def _is_already_completed(self, ticker: str) -> bool:
        return (self.output_dir / ticker / "complete_report.md").exists()

    def _build_config(self) -> dict:
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = self.profile_config.get("research_depth", 1)
        config["max_risk_discuss_rounds"] = self.profile_config.get("research_depth", 1)
        config["quick_think_llm"] = self.profile_config.get("shallow_thinker")
        config["deep_think_llm"] = self.profile_config.get("deep_think_llm")
        config["backend_url"] = self.profile_config.get("backend_url")
        config["llm_provider"] = self.profile_config.get("llm_provider", "openai").lower()
        config["google_thinking_level"] = self.profile_config.get("google_thinking_level")
        config["openai_reasoning_effort"] = self.profile_config.get("openai_reasoning_effort")
        config["anthropic_effort"] = self.profile_config.get("anthropic_effort")
        config["output_language"] = self.profile_config.get("output_language", "English")
        config["checkpoint_enabled"] = self.checkpoint
        return config

    def _run_single(self, ticker: str) -> dict:
        """Run analysis for a single ticker. Returns final state dict."""
        from cli.main import (
            ANALYST_ORDER,
            save_report_to_disk,
            run_translation_pipeline,
            update_analyst_statuses,
            update_research_team_status,
            classify_message_type,
        )

        config = self._build_config()
        selected_analyst_keys = [a for a in ANALYST_ORDER if a in self.profile_config.get("analysts", [])]
        if not selected_analyst_keys:
            selected_analyst_keys = ["market"]

        stats_handler = StatsCallbackHandler()
        graph = TradingAgentsGraph(
            selected_analyst_keys,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        init_state = graph.propagator.create_initial_state(ticker, self.profile_config.get("analysis_date"))
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        trace = []
        for chunk in graph.graph.stream(init_state, **args):
            for message in chunk.get("messages", []):
                msg_type, content = classify_message_type(message)
                if content and content.strip():
                    self.dashboard.add_message(msg_type, content)
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tc in message.tool_calls:
                        if isinstance(tc, dict):
                            self.dashboard.add_tool_call(tc["name"], tc.get("args", {}))
                        else:
                            self.dashboard.add_tool_call(tc.name, tc.args)

            update_analyst_statuses(self.dashboard, chunk)

            if chunk.get("investment_debate_state"):
                debate = chunk["investment_debate_state"]
                if debate.get("bull_history", "").strip() or debate.get("bear_history", "").strip():
                    update_research_team_status(self.dashboard, "in_progress")
                if debate.get("judge_decision", "").strip():
                    self.dashboard.set_agent_status("Research Manager", "completed")
                    self.dashboard.set_agent_status("Trader", "in_progress")

            if chunk.get("trader_investment_plan"):
                self.dashboard.set_agent_status("Trader", "completed")
                self.dashboard.set_agent_status("Aggressive Analyst", "in_progress")

            if chunk.get("risk_debate_state"):
                risk = chunk["risk_debate_state"]
                for role in ["aggressive", "conservative", "neutral"]:
                    hist = risk.get(f"{role}_history", "").strip()
                    if hist:
                        self.dashboard.set_agent_status(f"{role.title()} Analyst", "completed")
                judge = risk.get("judge_decision", "").strip()
                if judge:
                    self.dashboard.set_agent_status("Portfolio Manager", "completed")

            trace.append(chunk)

        final_state = trace[-1] if trace else {}

        # Save report
        ticker_dir = self.output_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        save_report_to_disk(final_state, ticker, ticker_dir)

        # Translation
        if config.get("output_language") == "Chinese":
            run_translation_pipeline(ticker_dir, config)

        # Extract summary
        self._extract_summary(ticker, final_state)
        return final_state

    def _extract_summary(self, ticker: str, final_state: dict) -> None:
        """Extract portfolio decision for batch summary."""
        import re
        decision = final_state.get("final_trade_decision", "")
        company = final_state.get("company_name", "")
        rating_match = re.search(r"(?:Rating|Decision)\s*[:：]\s*(\w+)", decision, re.IGNORECASE)
        entry_match = re.search(r"Entry\s*[:：]\s*([\d\-.—]+)", decision, re.IGNORECASE)
        stop_match = re.search(r"Stop\s*[:：]\s*([\d\-.—]+)", decision, re.IGNORECASE)
        size_match = re.search(r"Size\s*[:：]\s*([\d.%—]+)", decision, re.IGNORECASE)

        self.summaries[ticker] = {
            "company": company or ticker,
            "rating": rating_match.group(1) if rating_match else "—",
            "entry": entry_match.group(1) if entry_match else "—",
            "stop": stop_match.group(1) if stop_match else "—",
            "size": size_match.group(1) if size_match else "—",
        }

    def run(self) -> None:
        """Run the full batch."""
        layout = create_batch_layout()
        start_time = time.time()
        self.dashboard.update_progress(self.tickers[0] if self.tickers else None, 0, 0)

        with Live(layout, refresh_per_second=4) as live:
            for idx, ticker in enumerate(self.tickers):
                if self._is_already_completed(ticker):
                    self.completed_tickers.add(ticker)
                    continue

                self.dashboard.reset_for_next_stock()
                self.dashboard.update_progress(ticker, len(self.completed_tickers), len(self.failures))
                self.dashboard.set_agent_status("Market Analyst", "in_progress")
                update_batch_display(layout, self.dashboard, elapsed=time.time() - start_time)

                try:
                    self._run_single(ticker)
                    self.completed_tickers.add(ticker)
                except Exception as e:
                    self.failures[ticker] = str(e)
                    self.completed_tickers.add(ticker)
                    # Write failure log
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    failures_path = self.output_dir / "failures.log"
                    with open(failures_path, "a", encoding="utf-8") as f:
                        f.write(f"{ticker}: {e}\n")

                self.dashboard.update_progress(ticker, len(self.completed_tickers) - len(self.failures), len(self.failures))
                update_batch_display(layout, self.dashboard, elapsed=time.time() - start_time)

    def generate_summary(self) -> Path:
        """Generate batch_summary.md. Returns path."""
        lines = ["# Batch Analysis Report\n"]
        lines.append("| Ticker | Company | Rating | Entry | Stop | Size | Status |")
        lines.append("|--------|---------|--------|-------|------|------|--------|")

        all_tickers = sorted(
            set(self.tickers) | set(self.summaries.keys()) | set(self.failures.keys())
        )
        for ticker in all_tickers:
            if ticker in self.failures:
                lines.append(f"| {ticker} | — | — | — | — | — | ❌ {self.failures[ticker]} |")
            else:
                s = self.summaries.get(ticker, {})
                lines.append(
                    f"| {ticker} | {s.get('company', ticker)} | {s.get('rating', '—')} | "
                    f"{s.get('entry', '—')} | {s.get('stop', '—')} | {s.get('size', '—')} | ✅ |"
                )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "batch_summary.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

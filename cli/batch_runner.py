import os

# Batch mode is unattended — tqdm progress bars from akshare/yfinance/third-party
# libraries spam the terminal and break the Rich TUI layout. Disable globally.
os.environ["TQDM_DISABLE"] = "1"

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from cli.batch_dashboard import BatchDashboard, create_batch_layout, update_batch_display
from cli.stats_handler import StatsCallbackHandler
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from rich.live import Live
from rich.console import Console

console = Console()


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
        # Set by run() once the Live context owns these — _refresh_display() reads
        # them. When unset (e.g. tests calling _run_single directly), refresh is a no-op.
        self._layout = None
        self._start_time: Optional[float] = None

    def _refresh_display(self) -> None:
        """Push current dashboard state into the Live-managed layout.

        Without this call the dashboard mutations inside _run_single's stream
        loop never reach the screen — Live only re-renders the layout object
        it was given, and our updates target dashboard fields, not panels.
        Safe no-op when no Live context is active.
        """
        if self._layout is None or self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        update_batch_display(self._layout, self.dashboard, elapsed=elapsed)

    def _is_already_completed(self, ticker: str) -> bool:
        """Check if ticker was already analysed today.

        Scans the current output directory *and* all historical batch_* folders
        under the same ``reports/`` root, because each run creates a new
        timestamped directory.
        """
        today = datetime.now().date()

        # Candidate folder names: raw ticker + resolved suffix variants
        candidates = {ticker}
        try:
            from tradingagents.ticker_resolver import resolve_ticker
            resolved = resolve_ticker(ticker)
            candidates.add(resolved["ticker"])
        except Exception:
            pass

        def _is_fresh(path: Path) -> bool:
            if not path.exists():
                return False
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            return mtime.date() == today

        # 1. Check current batch directory
        for cand in candidates:
            if _is_fresh(self.output_dir / cand / "complete_report.md"):
                return True

        # 2. Check historical batch_* directories
        reports_dir = self.output_dir.parent
        if reports_dir.exists():
            for batch_dir in reports_dir.glob("batch_*"):
                for cand in candidates:
                    if _is_fresh(batch_dir / cand / "complete_report.md"):
                        return True

        return False

    def _build_config(self) -> dict:
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = self.profile_config.get("research_depth", 1)
        config["max_risk_discuss_rounds"] = self.profile_config.get("research_depth", 1)
        config["quick_think_llm"] = self.profile_config.get("shallow_thinker")
        config["deep_think_llm"] = self.profile_config.get("deep_thinker")
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
        from tradingagents.ticker_resolver import resolve_ticker

        # Resolve ticker (A-share numeric codes get .SS/.SZ/.BJ suffix)
        resolved = resolve_ticker(ticker)
        resolved_ticker = resolved["ticker"]
        company_name = resolved.get("company_name", "")

        config = self._build_config()
        selected_analyst_keys = [a for a in ANALYST_ORDER if a in self.profile_config.get("analysts", [])]
        if not selected_analyst_keys:
            selected_analyst_keys = ["market"]
        self.dashboard.selected_analysts = selected_analyst_keys

        stats_handler = StatsCallbackHandler()
        graph = TradingAgentsGraph(
            selected_analyst_keys,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        trade_date = self.profile_config.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        init_state = graph.propagator.create_initial_state(resolved_ticker, trade_date)
        if company_name:
            init_state["company_name"] = company_name
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

            self._refresh_display()
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

        self._layout = layout
        self._start_time = start_time

        with Live(layout, refresh_per_second=4) as live:
            # Push an initial frame so the user sees something other than empty
            # panels for the few seconds before the first node fires.
            update_batch_display(layout, self.dashboard, elapsed=0.0)

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

        # Live closed — release the layout reference so any stray _refresh_display
        # call from finalization code becomes a no-op instead of writing to a dead layout.
        self._layout = None
        self._start_time = None

    def generate_summary(self) -> Path:
        """Generate batch_summary.md and batch_summary.json. Returns path to markdown."""
        lines = ["# Batch Analysis Report\n"]
        lines.append("| Ticker | Company | Rating | Entry | Stop | Size | Status | Details |")
        lines.append("|--------|---------|--------|-------|------|------|--------|---------|")

        all_tickers = sorted(
            set(self.tickers) | set(self.summaries.keys()) | set(self.failures.keys())
        )
        json_rows = []
        for ticker in all_tickers:
            if ticker in self.failures:
                lines.append(f"| {ticker} | — | — | — | — | — | ❌ | — |")
                json_rows.append({
                    "ticker": ticker,
                    "company": None,
                    "rating": None,
                    "entry": None,
                    "stop": None,
                    "size": None,
                    "status": "failed",
                    "error": self.failures[ticker],
                })
            else:
                s = self.summaries.get(ticker, {})
                lines.append(
                    f"| {ticker} | {s.get('company', ticker)} | {s.get('rating', '—')} | "
                    f"{s.get('entry', '—')} | {s.get('stop', '—')} | {s.get('size', '—')} | ✅ | "
                    f"[Report](./{ticker}/complete_report.md) |"
                )
                json_rows.append({
                    "ticker": ticker,
                    "company": s.get("company", ticker),
                    "rating": s.get("rating"),
                    "entry": s.get("entry"),
                    "stop": s.get("stop"),
                    "size": s.get("size"),
                    "status": "success",
                    "error": None,
                })

        # Append failure details so errors are still readable without widening the table
        if self.failures:
            lines.append("\n## Failures\n")
            for ticker, error in sorted(self.failures.items()):
                lines.append(f"- **{ticker}**: {error}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.output_dir / "batch_summary.md"
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Write JSON summary for downstream processing
        json_path = self.output_dir / "batch_summary.json"
        json_path.write_text(json.dumps(json_rows, ensure_ascii=False, indent=2), encoding="utf-8")

        # Translate if Chinese
        if self.profile_config.get("output_language") == "Chinese":
            from cli.main import _translate_content, _split_translation_chunks
            from tradingagents.llm_clients.factory import create_llm_client
            try:
                provider = self.profile_config.get("llm_provider", "openai")
                model = self.profile_config.get("quick_think_llm") or self.profile_config.get("deep_think_llm")
                base_url = self.profile_config.get("backend_url")
                if model:
                    client = create_llm_client(provider, model, base_url)
                    llm = client.get_llm()
                    content = md_path.read_text(encoding="utf-8")
                    chunks = _split_translation_chunks(content)
                    chunk_info = f" ({len(chunks)} chunks)" if len(chunks) > 1 else ""
                    translated = _translate_content(llm, content)
                    cn_path = self.output_dir / "batch_summary_CN.md"
                    cn_path.write_text(translated, encoding="utf-8")
                    console.print(f"  [green]✓[/green] [dim]{cn_path.name}{chunk_info}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to translate batch summary: {e}[/yellow]")

        return md_path

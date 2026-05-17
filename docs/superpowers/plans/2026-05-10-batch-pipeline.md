# Batch Pipeline & Profile System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a profile system to save analysis preferences, a watchlist system to manage stock lists, and a batch pipeline with auto-save, auto-translation, and a batch dashboard for unattended multi-stock analysis.

**Architecture:** File-driven persistence (JSON profiles, plain-text watchlists) with a unified `analyze` CLI entry point. Core logic lives in four new focused CLI modules; `main.py` gains mode-selection and batch-orchestration wiring.

**Tech Stack:** Python 3.11+, Typer, Questionary, Rich, pytest.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `cli/profiles.py` | Create | Profile CRUD: save, load, list, delete. |
| `cli/watchlists.py` | Create | Watchlist CRUD: save, load, list, parse. |
| `cli/batch_dashboard.py` | Create | Rich Live layout for batch monitoring. |
| `cli/batch_runner.py` | Create | Orchestrates multi-stock queue, runs graph per ticker, handles failures, generates summary. |
| `cli/main.py` | Modify | Unified entry point: mode selection, CLI args (`--profile`, `--watchlist`, `--tickers`), wire batch runner. |
| `tests/cli/test_profiles.py` | Create | Unit tests for profile CRUD. |
| `tests/cli/test_watchlists.py` | Create | Unit tests for watchlist CRUD. |
| `tests/cli/test_batch_runner.py` | Create | Unit tests for batch runner core logic (mocked graph). |
| `tests/cli/test_batch_dashboard.py` | Create | Unit tests for dashboard layout helpers. |

---

### Task 1: Profile System

**Files:**
- Create: `cli/profiles.py`
- Test: `tests/cli/test_profiles.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_profiles.py`:

```python
import json
import pytest
from pathlib import Path
from cli.profiles import save_profile, load_profile, list_profiles, delete_profile


@pytest.fixture(autouse=True)
def _mock_profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.profiles._PROFILES_DIR", tmp_path / "profiles")


def test_save_and_load_profile():
    config = {
        "analysts": ["market", "news"],
        "research_depth": 3,
        "llm_provider": "openai",
        "output_language": "Chinese",
    }
    path = save_profile("my_profile", config)
    assert path.exists()
    loaded = load_profile("my_profile")
    assert loaded["name"] == "my_profile"
    assert loaded["config"] == config


def test_load_profile_not_found():
    with pytest.raises(FileNotFoundError):
        load_profile("nonexistent")


def test_list_profiles():
    save_profile("alpha", {"llm_provider": "openai"})
    save_profile("beta", {"llm_provider": "anthropic"})
    names = list_profiles()
    assert sorted(names) == ["alpha", "beta"]


def test_delete_profile():
    save_profile("to_delete", {"llm_provider": "openai"})
    delete_profile("to_delete")
    assert "to_delete" not in list_profiles()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_profiles.py -v`
Expected: FAIL with import errors (module not defined)

- [ ] **Step 3: Write minimal implementation**

Create `cli/profiles.py`:

```python
import json
from pathlib import Path
from typing import Optional

_PROFILES_DIR = Path.home() / ".tradingagents" / "profiles"


def _ensure_dir() -> Path:
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR


def save_profile(name: str, config: dict) -> Path:
    """Save a profile to disk. Returns the file path."""
    directory = _ensure_dir()
    path = directory / f"{name}.json"
    payload = {
        "name": name,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "config": config,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_profile(name: str) -> dict:
    """Load a profile by name. Raises FileNotFoundError if missing."""
    path = _ensure_dir() / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile '{name}' not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_profiles() -> list[str]:
    """Return a list of saved profile names."""
    directory = _ensure_dir()
    return sorted([p.stem for p in directory.glob("*.json")])


def delete_profile(name: str) -> None:
    """Delete a profile by name."""
    path = _ensure_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_profiles.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_profiles.py cli/profiles.py
git commit -m "feat: add profile persistence system

feat: 新增 Profile 持久化系统，支持保存、加载、列出和删除分析配置"
```

---

### Task 2: Watchlist System

**Files:**
- Create: `cli/watchlists.py`
- Test: `tests/cli/test_watchlists.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_watchlists.py`:

```python
import pytest
from cli.watchlists import (
    save_watchlist,
    load_watchlist,
    list_watchlists,
    parse_watchlist_content,
)


@pytest.fixture(autouse=True)
def _mock_watchlists_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.watchlists._WATCHLISTS_DIR", tmp_path / "watchlists")


def test_save_and_load_watchlist():
    tickers = ["AAPL", "MSFT", "GOOGL"]
    path = save_watchlist("tech", tickers)
    assert path.exists()
    loaded = load_watchlist("tech")
    assert loaded == tickers


def test_parse_watchlist_content():
    raw = """# Tech stocks
AAPL
MSFT

# Energy
TSLA
"""
    result = parse_watchlist_content(raw)
    assert result == ["AAPL", "MSFT", "TSLA"]


def test_load_watchlist_not_found():
    with pytest.raises(FileNotFoundError):
        load_watchlist("nonexistent")


def test_list_watchlists():
    save_watchlist("alpha", ["A"])
    save_watchlist("beta", ["B"])
    names = list_watchlists()
    assert sorted(names) == ["alpha", "beta"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_watchlists.py -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

Create `cli/watchlists.py`:

```python
from pathlib import Path

_WATCHLISTS_DIR = Path.home() / ".tradingagents" / "watchlists"


def _ensure_dir() -> Path:
    _WATCHLISTS_DIR.mkdir(parents=True, exist_ok=True)
    return _WATCHLISTS_DIR


def parse_watchlist_content(content: str) -> list[str]:
    """Parse watchlist text: one ticker per line, ignore comments and blanks."""
    tickers = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tickers.append(stripped)
    return tickers


def save_watchlist(name: str, tickers: list[str]) -> Path:
    """Save a watchlist to disk. Returns the file path."""
    directory = _ensure_dir()
    path = directory / f"{name}.txt"
    lines = "\n".join(tickers) + "\n"
    path.write_text(lines, encoding="utf-8")
    return path


def load_watchlist(name: str) -> list[str]:
    """Load a watchlist by name. Raises FileNotFoundError if missing."""
    path = _ensure_dir() / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Watchlist '{name}' not found at {path}")
    return parse_watchlist_content(path.read_text(encoding="utf-8"))


def list_watchlists() -> list[str]:
    """Return a list of saved watchlist names."""
    directory = _ensure_dir()
    return sorted([p.stem for p in directory.glob("*.txt")])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_watchlists.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_watchlists.py cli/watchlists.py
git commit -m "feat: add watchlist persistence system

feat: 新增 Watchlist 持久化系统，支持保存、加载、列出和解析"
```

---

### Task 3: Batch Dashboard Layout

**Files:**
- Create: `cli/batch_dashboard.py`
- Test: `tests/cli/test_batch_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_batch_dashboard.py`:

```python
from cli.batch_dashboard import BatchDashboard


def test_dashboard_initial_state():
    bd = BatchDashboard(total=5, profile_name="test")
    assert bd.total == 5
    assert bd.completed == 0
    assert bd.failed == 0
    assert bd.current_ticker is None


def test_dashboard_update_progress():
    bd = BatchDashboard(total=5, profile_name="test")
    bd.update_progress(current_ticker="AAPL", completed=2, failed=1)
    assert bd.current_ticker == "AAPL"
    assert bd.completed == 2
    assert bd.failed == 1


def test_dashboard_agent_status():
    bd = BatchDashboard(total=3, profile_name="test")
    bd.set_agent_status("Market Analyst", "completed")
    bd.set_agent_status("Trader", "in_progress")
    assert bd.agent_status["Market Analyst"] == "completed"
    assert bd.agent_status["Trader"] == "in_progress"


def test_dashboard_reset_for_next_stock():
    bd = BatchDashboard(total=3, profile_name="test")
    bd.set_agent_status("Market Analyst", "completed")
    bd.reset_for_next_stock()
    assert bd.agent_status == {}
    assert bd.current_report is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_batch_dashboard.py -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

Create `cli/batch_dashboard.py`:

```python
from typing import Optional
from collections import deque


class BatchDashboard:
    """Holds mutable state for the batch analysis dashboard."""

    def __init__(self, total: int, profile_name: str):
        self.total = total
        self.profile_name = profile_name
        self.completed = 0
        self.failed = 0
        self.current_ticker: Optional[str] = None
        self.agent_status: dict[str, str] = {}
        self.current_report: Optional[str] = None
        self.messages: deque = deque(maxlen=100)
        self.tool_calls: deque = deque(maxlen=100)

    def update_progress(self, current_ticker: str, completed: int, failed: int) -> None:
        self.current_ticker = current_ticker
        self.completed = completed
        self.failed = failed

    def set_agent_status(self, agent: str, status: str) -> None:
        self.agent_status[agent] = status

    def set_current_report(self, report: str) -> None:
        self.current_report = report

    def add_message(self, msg_type: str, content: str) -> None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages.append((timestamp, msg_type, content))

    def add_tool_call(self, tool_name: str, args: dict) -> None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.tool_calls.append((timestamp, tool_name, args))

    def reset_for_next_stock(self) -> None:
        """Clear per-stock state when moving to the next ticker."""
        self.agent_status.clear()
        self.current_report = None
        self.messages.clear()
        self.tool_calls.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_batch_dashboard.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_batch_dashboard.py cli/batch_dashboard.py
git commit -m "feat: add batch dashboard state holder

feat: 新增 BatchDashboard 状态管理类，用于批量监控面板"
```

---

### Task 4: Batch Dashboard Renderer

**Files:**
- Create: `cli/batch_dashboard.py` (append rendering functions)

- [ ] **Step 1: Add rendering functions to `cli/batch_dashboard.py`**

Append to `cli/batch_dashboard.py`:

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich import box
from rich.text import Text
from rich.spinner import Spinner
from rich.rule import Rule
from rich.markdown import Markdown


def create_batch_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_column(
        Layout(name="upper", ratio=3), Layout(name="analysis", ratio=5)
    )
    layout["upper"].split_row(
        Layout(name="progress", ratio=2), Layout(name="messages", ratio=3)
    )
    return layout


def render_batch_header(layout: Layout, dashboard: BatchDashboard, elapsed: Optional[float] = None) -> None:
    elapsed_str = ""
    if elapsed is not None:
        elapsed_str = f"  |  Elapsed: {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
    header_text = (
        f"Batch: {dashboard.profile_name}  |  "
        f"Progress: {dashboard.completed} / {dashboard.total}  |  "
        f"Current: {dashboard.current_ticker or '-'}"
        f"{elapsed_str}"
    )
    layout["header"].update(
        Panel(header_text, border_style="green", padding=(1, 2))
    )


def render_progress_panel(layout: Layout, dashboard: BatchDashboard) -> None:
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.SIMPLE_HEAD,
        padding=(0, 2),
        expand=True,
    )
    table.add_column("Team", style="cyan", justify="center", width=20)
    table.add_column("Agent", style="green", justify="center", width=20)
    table.add_column("Status", style="yellow", justify="center", width=20)

    teams = {
        "Analyst Team": ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"],
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    for team, agents in teams.items():
        active = [a for a in agents if a in dashboard.agent_status]
        if not active:
            continue
        for idx, agent in enumerate(active):
            status = dashboard.agent_status.get(agent, "pending")
            if status == "in_progress":
                cell = Spinner("dots", text="[blue]in_progress[/blue]", style="bold cyan")
            else:
                color = {"pending": "yellow", "completed": "green", "error": "red"}.get(status, "white")
                cell = f"[{color}]{status}[/{color}]"
            table.add_row(team if idx == 0 else "", agent, cell)
        table.add_row("─" * 20, "─" * 20, "─" * 20, style="dim")

    layout["progress"].update(
        Panel(table, title="Progress", border_style="cyan", padding=(1, 2))
    )


def render_messages_panel(layout: Layout, dashboard: BatchDashboard) -> None:
    table = Table(
        show_header=True,
        header_style="bold magenta",
        expand=True,
        box=box.MINIMAL,
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("Time", style="cyan", width=8, justify="center")
    table.add_column("Type", style="green", width=10, justify="center")
    table.add_column("Content", style="white", no_wrap=False, ratio=1)

    all_items = []
    for ts, tool_name, args in dashboard.tool_calls:
        all_items.append((ts, "Tool", f"{tool_name}: {args}"))
    for ts, msg_type, content in dashboard.messages:
        content_str = str(content)[:200]
        all_items.append((ts, msg_type, content_str))

    all_items.sort(key=lambda x: x[0], reverse=True)
    for ts, msg_type, content in all_items[:12]:
        table.add_row(ts, msg_type, Text(content, overflow="fold"))

    layout["messages"].update(
        Panel(table, title="Messages & Tools", border_style="blue", padding=(1, 2))
    )


def render_analysis_panel(layout: Layout, dashboard: BatchDashboard) -> None:
    if dashboard.current_report:
        layout["analysis"].update(
            Panel(Markdown(dashboard.current_report), title="Current Report", border_style="green", padding=(1, 2))
        )
    else:
        layout["analysis"].update(
            Panel("[italic]Waiting for analysis report...[/italic]", title="Current Report", border_style="green", padding=(1, 2))
        )


def render_footer(layout: Layout, dashboard: BatchDashboard, llm_calls: int = 0, tool_calls: int = 0) -> None:
    stats = f"Completed: {dashboard.completed} | Failed: {dashboard.failed} | Remaining: {dashboard.total - dashboard.completed - dashboard.failed}"
    if llm_calls or tool_calls:
        stats += f"  |  LLM: {llm_calls} | Tools: {tool_calls}"
    layout["footer"].update(
        Panel(Text(stats, justify="center"), border_style="grey50")
    )


def update_batch_display(layout: Layout, dashboard: BatchDashboard, elapsed: Optional[float] = None, llm_calls: int = 0, tool_calls: int = 0) -> None:
    render_batch_header(layout, dashboard, elapsed)
    render_progress_panel(layout, dashboard)
    render_messages_panel(layout, dashboard)
    render_analysis_panel(layout, dashboard)
    render_footer(layout, dashboard, llm_calls, tool_calls)
```

- [ ] **Step 2: Run a quick import smoke test**

Run: `python -c "from cli.batch_dashboard import BatchDashboard, create_batch_layout, update_batch_display; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add cli/batch_dashboard.py
git commit -m "feat: add batch dashboard renderer

feat: 新增批量监控面板的 Rich Live 渲染函数"
```

---

### Task 5: Batch Runner Core

**Files:**
- Create: `cli/batch_runner.py`
- Test: `tests/cli/test_batch_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_batch_runner.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from cli.batch_runner import BatchRunner


@pytest.fixture(autouse=True)
def _mock_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_batch_runner_skips_completed():
    """If a ticker already has complete_report.md, skip it."""
    runner = BatchRunner(
        tickers=["AAPL"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=Path("/tmp/reports"),
    )
    # Simulate pre-existing report
    ticker_dir = runner.output_dir / "AAPL"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "complete_report.md").write_text("done")

    with patch.object(runner, "_run_single") as mock_run:
        runner.run()
        mock_run.assert_not_called()


def test_batch_runner_records_failure():
    """If _run_single raises, record failure and continue."""
    runner = BatchRunner(
        tickers=["AAPL", "MSFT"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=Path("/tmp/reports"),
    )

    def side_effect(ticker):
        if ticker == "AAPL":
            raise RuntimeError("API error")

    with patch.object(runner, "_run_single", side_effect=side_effect):
        runner.run()

    assert runner.failures == {"AAPL": "API error"}
    assert "AAPL" in runner.completed_tickers
    assert "MSFT" in runner.completed_tickers


def test_generate_summary_creates_markdown():
    runner = BatchRunner(
        tickers=["AAPL", "MSFT"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=Path("/tmp/reports"),
    )
    runner.summaries = {
        "AAPL": {"rating": "Buy", "entry": "210", "stop": "200", "size": "5%", "company": "Apple"},
        "MSFT": {"rating": "Hold", "entry": "—", "stop": "—", "size": "—", "company": "Microsoft"},
    }
    runner.failures = {"TSLA": "Invalid ticker"}
    path = runner.generate_summary()
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "AAPL" in content
    assert "Buy" in content
    assert "TSLA" in content
    assert "Invalid ticker" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_batch_runner.py -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

Create `cli/batch_runner.py`:

```python
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

        for ticker in self.tickers:
            if ticker in self.failures:
                lines.append(f"| {ticker} | — | — | — | — | — | ❌ {self.failures[ticker]} |")
            else:
                s = self.summaries.get(ticker, {})
                lines.append(
                    f"| {ticker} | {s.get('company', ticker)} | {s.get('rating', '—')} | "
                    f"{s.get('entry', '—')} | {s.get('stop', '—')} | {s.get('size', '—')} | ✅ |"
                )

        path = self.output_dir / "batch_summary.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_batch_runner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/cli/test_batch_runner.py cli/batch_runner.py
git commit -m "feat: add batch runner for unattended multi-stock analysis

feat: 新增 BatchRunner，支持自动跳过已完成股票、失败记录、批次汇总生成"
```

---

### Task 6: CLI Main Integration — Mode Selection

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Add imports and helper functions**

At the top of `cli/main.py`, add imports:

```python
from cli.profiles import save_profile, load_profile, list_profiles
from cli.watchlists import save_watchlist, load_watchlist, list_watchlists
from cli.batch_runner import BatchRunner
```

Add new helper functions after `get_analysis_date()` (around line 646):

```python
def _parse_tickers_input(raw: str) -> list[str]:
    """Parse comma-separated ticker input into a clean list."""
    return [t.strip() for t in raw.split(",") if t.strip()]


def ask_mode() -> str:
    """Ask user to choose between batch watchlist scan or custom ticker query."""
    import questionary
    choice = questionary.select(
        "Select run mode:",
        choices=[
            questionary.Choice("批量扫描 Watchlist", "batch"),
            questionary.Choice("查询自选股票（支持单只或多只，逗号分隔）", "single"),
        ],
        style=questionary.Style([
            ("selected", "fg:green noinherit"),
            ("highlighted", "fg:green noinherit"),
            ("pointer", "fg:green noinherit"),
        ]),
    ).ask()
    if choice is None:
        console.print("[red]No mode selected. Exiting...[/red]")
        exit(1)
    return choice


def select_watchlist_interactive() -> tuple[str, list[str]]:
    """Let user pick a saved watchlist or import from file. Returns (name, tickers)."""
    import questionary
    existing = list_watchlists()
    choices = []
    for name in existing:
        try:
            tickers = load_watchlist(name)
            choices.append(questionary.Choice(f"{name}  ({', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''})", value=(name, tickers)))
        except Exception:
            choices.append(questionary.Choice(name, value=(name, [])))
    choices.append(questionary.Choice("Import from file...", value=("__import__", [])))

    choice = questionary.select(
        "Select watchlist:",
        choices=choices,
        style=questionary.Style([
            ("selected", "fg:yellow noinherit"),
            ("highlighted", "fg:yellow noinherit"),
            ("pointer", "fg:yellow noinherit"),
        ]),
    ).ask()

    if choice is None:
        console.print("[red]No watchlist selected. Exiting...[/red]")
        exit(1)

    name, tickers = choice
    if name == "__import__":
        file_path = questionary.text(
            "Enter watchlist file path:",
            validate=lambda x: len(x.strip()) > 0 or "Please enter a valid path.",
        ).ask().strip()
        from cli.watchlists import parse_watchlist_content
        tickers = parse_watchlist_content(Path(file_path).read_text(encoding="utf-8"))
        name = Path(file_path).stem
    return name, tickers


def select_profile_interactive() -> dict:
    """Let user pick a saved profile or create a new one. Returns profile config dict."""
    import questionary
    existing = list_profiles()
    if existing:
        choices = []
        for name in existing:
            try:
                prof = load_profile(name)
                cfg = prof.get("config", {})
                summary = f"({cfg.get('llm_provider', '?')}, {cfg.get('deep_think_llm', '?')}, {len(cfg.get('analysts', []))} analysts, {cfg.get('output_language', '?')})"
                choices.append(questionary.Choice(f"{name}  {summary}", value=name))
            except Exception:
                choices.append(questionary.Choice(name, value=name))
        choices.append(questionary.Choice("Create new profile...", value="__new__"))
        choice = questionary.select(
            "Select profile:",
            choices=choices,
            style=questionary.Style([
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]),
        ).ask()
        if choice is None:
            console.print("[red]No profile selected. Exiting...[/red]")
            exit(1)
        if choice != "__new__":
            return load_profile(choice)["config"]
    # Fall through to create new profile
    return None
```

- [ ] **Step 2: Modify `get_user_selections()` to support multi-ticker input**

Replace the ticker input section in `get_user_selections()` (around line 503-525):

Old:
```python
    # Step 1: Ticker symbol
    console.print(
        create_question_box(
            "Step 1: Ticker Symbol",
            "Enter the exact ticker symbol to analyze, including exchange suffix when needed (examples: SPY, CNC.TO, 7203.T, 0700.HK)",
            "SPY",
        )
    )
    selected_ticker = get_ticker()

    # Resolve ticker and display confirmation
    from tradingagents.ticker_resolver import resolve_ticker
    try:
        resolved = resolve_ticker(selected_ticker)
        if resolved.get("company_name"):
            console.print(
                f"[green]已解析: {resolved['company_name']} ({resolved['ticker']})[/green]"
            )
        else:
            console.print(f"[green]已解析: {resolved['ticker']}[/green]")
        selected_ticker = resolved["ticker"]
    except Exception as e:
        console.print(f"[yellow]解析提示: {e}[/yellow]")
```

New:
```python
    # Step 1: Ticker symbol(s)
    console.print(
        create_question_box(
            "Step 1: Ticker Symbol",
            "Enter ticker symbol(s) to analyze, comma-separated for multiple (examples: SPY, AAPL,MSFT,GOOGL)",
            "SPY",
        )
    )
    raw_tickers = get_ticker()
    tickers = _parse_tickers_input(raw_tickers)

    # Resolve first ticker for display; skip bulk resolution to save time
    from tradingagents.ticker_resolver import resolve_ticker
    selected_tickers = []
    for t in tickers:
        try:
            resolved = resolve_ticker(t)
            selected_tickers.append(resolved["ticker"])
        except Exception as e:
            console.print(f"[yellow]解析提示 {t}: {e}[/yellow]")
            selected_tickers.append(t)

    if len(selected_tickers) == 1:
        selected_ticker = selected_tickers[0]
    else:
        selected_ticker = selected_tickers  # list for batch mode
```

Also update the return statement of `get_user_selections()` to include the tickers list:

At the end of `get_user_selections()`, change:
```python
    return {
        "ticker": selected_ticker,
```
to:
```python
    return {
        "ticker": selected_ticker if isinstance(selected_ticker, str) else selected_tickers[0],
        "tickers": selected_tickers if isinstance(selected_ticker, list) else [selected_ticker],
```

- [ ] **Step 3: Add `run_batch_analysis()` function**

Add after `run_analysis()` (around line 1317):

```python
def run_batch_analysis(tickers: list[str], profile_config: dict, checkpoint: bool = False):
    """Run unattended batch analysis for multiple tickers."""
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path.cwd() / "reports" / f"batch_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = BatchRunner(
        tickers=tickers,
        profile_config=profile_config,
        output_dir=output_dir,
        checkpoint=checkpoint,
    )
    runner.run()

    # Generate summary
    summary_path = runner.generate_summary()
    console.print("\n[bold cyan]Batch Complete![/bold cyan]\n")
    console.print(f"Total: {len(tickers)}  |  Success: {len(runner.completed_tickers) - len(runner.failures)}  |  Failed: {len(runner.failures)}")
    console.print(f"[green]Reports:[/green] {output_dir.resolve()}")
    console.print(f"[green]Summary:[/green] {summary_path.name}")

    # Print summary table
    from rich.table import Table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Ticker", style="cyan")
    table.add_column("Company", style="green")
    table.add_column("Rating", style="yellow")
    table.add_column("Entry", style="white")
    table.add_column("Stop", style="white")
    table.add_column("Size", style="white")
    table.add_column("Status", style="green")

    for ticker in tickers:
        if ticker in runner.failures:
            table.add_row(ticker, "—", "—", "—", "—", "—", f"❌ {runner.failures[ticker]}")
        else:
            s = runner.summaries.get(ticker, {})
            table.add_row(
                ticker,
                s.get("company", ticker),
                s.get("rating", "—"),
                s.get("entry", "—"),
                s.get("stop", "—"),
                s.get("size", "—"),
                "✅",
            )
    console.print(table)

    # Prompt to save as watchlist if not from one
    save_wl = typer.prompt("Save ticker list as watchlist?", default="N").strip().upper()
    if save_wl in ("Y", "YES"):
        wl_name = typer.prompt("Watchlist name", default=f"batch_{timestamp}").strip()
        save_watchlist(wl_name, tickers)
        console.print(f"[green]✓ Watchlist saved:[/green] {wl_name}")
```

- [ ] **Step 4: Modify `analyze()` Typer command**

Replace the existing `analyze()` command (around line 1318):

Old:
```python
@app.command()
def analyze(
    checkpoint: bool = typer.Option(
        False,
        "--checkpoint",
        help="Enable checkpoint/resume: save state after each node so a crashed run can resume.",
    ),
    clear_checkpoints: bool = typer.Option(
        False,
        "--clear-checkpoints",
        help="Delete all saved checkpoints before running (force fresh start).",
    ),
):
    if clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints
        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        console.print(f"[yellow]Cleared {n} checkpoint(s).[/yellow]")
    run_analysis(checkpoint=checkpoint)
```

New:
```python
@app.command()
def analyze(
    checkpoint: bool = typer.Option(
        False,
        "--checkpoint",
        help="Enable checkpoint/resume: save state after each node so a crashed run can resume.",
    ),
    clear_checkpoints: bool = typer.Option(
        False,
        "--clear-checkpoints",
        help="Delete all saved checkpoints before running (force fresh start).",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="Use a saved profile for analysis configuration.",
    ),
    watchlist: Optional[str] = typer.Option(
        None,
        "--watchlist",
        help="Run batch analysis using a saved watchlist (by name or file path).",
    ),
    tickers: Optional[str] = typer.Option(
        None,
        "--tickers",
        help="Comma-separated tickers for batch analysis (e.g. AAPL,MSFT,GOOGL).",
    ),
):
    if clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints
        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        console.print(f"[yellow]Cleared {n} checkpoint(s).[/yellow]")

    # Direct batch mode via CLI args
    if profile or watchlist or tickers:
        # Load profile
        if profile:
            try:
                prof = load_profile(profile)
                profile_config = prof["config"]
            except Exception as e:
                console.print(f"[red]Failed to load profile '{profile}': {e}[/red]")
                raise typer.Exit(1)
        else:
            profile_config = DEFAULT_CONFIG.copy()
            profile_config["analysts"] = ["market"]

        # Load tickers
        if tickers:
            ticker_list = _parse_tickers_input(tickers)
        elif watchlist:
            try:
                ticker_list = load_watchlist(watchlist)
            except Exception:
                # Try as file path
                from cli.watchlists import parse_watchlist_content
                ticker_list = parse_watchlist_content(Path(watchlist).read_text(encoding="utf-8"))
        else:
            console.print("[red]Batch mode requires --tickers or --watchlist.[/red]")
            raise typer.Exit(1)

        if not ticker_list:
            console.print("[red]No tickers to analyze.[/red]")
            raise typer.Exit(1)

        run_batch_analysis(ticker_list, profile_config, checkpoint=checkpoint)
        return

    # Interactive mode
    mode = ask_mode()
    if mode == "batch":
        _, ticker_list = select_watchlist_interactive()
        profile_config = select_profile_interactive()
        if profile_config is None:
            # User chose to create new profile — run the normal selection flow
            selections = get_user_selections()
            profile_config = {
                "analysts": [a.value for a in selections["analysts"]],
                "research_depth": selections["research_depth"],
                "llm_provider": selections["llm_provider"],
                "backend_url": selections["backend_url"],
                "shallow_thinker": selections["shallow_thinker"],
                "deep_thinker": selections["deep_thinker"],
                "google_thinking_level": selections.get("google_thinking_level"),
                "openai_reasoning_effort": selections.get("openai_reasoning_effort"),
                "anthropic_effort": selections.get("anthropic_effort"),
                "output_language": selections.get("output_language", "English"),
                "analysis_date": selections["analysis_date"],
            }
            save_prof = typer.prompt("Save this configuration as a profile?", default="Y").strip().upper()
            if save_prof in ("Y", "YES", ""):
                prof_name = typer.prompt("Profile name", default="default").strip()
                save_profile(prof_name, profile_config)
                console.print(f"[green]✓ Profile saved:[/green] {prof_name}")

        if len(ticker_list) == 1:
            # Fall back to single-stock flow for one ticker
            run_analysis(checkpoint=checkpoint)
        else:
            run_batch_analysis(ticker_list, profile_config, checkpoint=checkpoint)
    else:
        # Single / custom mode
        selections = get_user_selections()
        tickers = selections.get("tickers", [selections["ticker"]])
        if len(tickers) > 1:
            # Batch mode for multiple custom tickers
            profile_config = {
                "analysts": [a.value for a in selections["analysts"]],
                "research_depth": selections["research_depth"],
                "llm_provider": selections["llm_provider"],
                "backend_url": selections["backend_url"],
                "shallow_thinker": selections["shallow_thinker"],
                "deep_thinker": selections["deep_thinker"],
                "google_thinking_level": selections.get("google_thinking_level"),
                "openai_reasoning_effort": selections.get("openai_reasoning_effort"),
                "anthropic_effort": selections.get("anthropic_effort"),
                "output_language": selections.get("output_language", "English"),
                "analysis_date": selections["analysis_date"],
            }
            run_batch_analysis(tickers, profile_config, checkpoint=checkpoint)
        else:
            run_analysis(checkpoint=checkpoint)
```

- [ ] **Step 5: Run smoke test**

Run: `uv run python -c "from cli.main import app; print('import OK')"`
Expected: import OK (no syntax errors)

Run: `uv run pytest tests/cli/ -v`
Expected: All 11 tests pass

- [ ] **Step 6: Commit**

```bash
git add cli/main.py
git commit -m "feat: integrate batch pipeline into analyze CLI entry point

feat: 在 analyze 命令中集成批量分析入口，支持模式选择、Profile/Watchlist 交互选择和命令行参数"
```

---

### Task 7: Add Batch Summary Translation

**Files:**
- Modify: `cli/batch_runner.py`

- [ ] **Step 1: Translate batch_summary.md when output_language is Chinese**

In `cli/batch_runner.py`, modify `generate_summary()` to also translate if needed:

After generating `batch_summary.md`, add:

```python
    def generate_summary(self) -> Path:
        # ... existing code ...
        path = self.output_dir / "batch_summary.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Translate if Chinese
        if self.profile_config.get("output_language") == "Chinese":
            from cli.main import _translate_content
            from tradingagents.llm_clients.factory import create_llm_client
            try:
                provider = self.profile_config.get("llm_provider", "openai")
                model = self.profile_config.get("quick_think_llm") or self.profile_config.get("deep_think_llm")
                base_url = self.profile_config.get("backend_url")
                if model:
                    client = create_llm_client(provider, model, base_url)
                    llm = client.get_llm()
                    translated = _translate_content(llm, path.read_text(encoding="utf-8"))
                    cn_path = self.output_dir / "batch_summary_CN.md"
                    cn_path.write_text(translated, encoding="utf-8")
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to translate batch summary: {e}[/yellow]")

        return path
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/cli/test_batch_runner.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add cli/batch_runner.py
git commit -m "feat: auto-translate batch summary to Chinese

feat: 批量汇总报告支持自动翻译成中文"
```

---

## Self-Review

**1. Spec coverage:**
- Profile CRUD → Task 1
- Watchlist CRUD → Task 2
- Batch Dashboard state + renderer → Tasks 3-4
- Batch runner with skip/fail/summary → Task 5
- CLI mode selection and integration → Task 6
- Batch summary translation → Task 7
- No gaps found.

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later", "add appropriate error handling", or "similar to Task N" found.
- All code blocks contain concrete implementations.

**3. Type consistency:**
- `BatchDashboard` methods used in Task 5 (`set_agent_status`, `reset_for_next_stock`, etc.) match definitions in Task 3.
- `BatchRunner` constructor signature used in tests (Task 5) matches implementation.
- `save_report_to_disk`, `run_translation_pipeline`, `classify_message_type` referenced in Task 5 all exist in `cli/main.py`.

**4. Scope check:**
- Plan is focused on the batch pipeline feature.
- No unrelated refactoring included.
- `checkpoint_enabled` is wired through but detailed checkpoint logic reuse is left to existing code.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-batch-pipeline.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

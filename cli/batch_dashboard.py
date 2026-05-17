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
        self.selected_analysts: list[str] = []
        self.report_sections: dict[str, Optional[str]] = {}

    def update_progress(self, current_ticker: str, completed: int, failed: int) -> None:
        self.current_ticker = current_ticker
        self.completed = completed
        self.failed = failed

    def set_agent_status(self, agent: str, status: str) -> None:
        self.agent_status[agent] = status

    update_agent_status = set_agent_status

    def set_current_report(self, report: str) -> None:
        self.current_report = report

    def update_report_section(self, section_name: str, content: str) -> None:
        self.report_sections[section_name] = content

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
        self.report_sections.clear()


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
        "Analyst Team": ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst", "Governance Analyst", "Industry Analyst"],
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

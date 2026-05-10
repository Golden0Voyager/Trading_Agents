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

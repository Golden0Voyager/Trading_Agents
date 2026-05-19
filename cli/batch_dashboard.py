"""Batch-specific dashboard that extends the generic AnalysisDashboard."""

from typing import Optional

from cli.dashboard import AnalysisDashboard


class BatchDashboard(AnalysisDashboard):
    """Holds mutable state for the batch analysis dashboard.

    Extends AnalysisDashboard with batch-level counters and
    delegates all rendering to cli.dashboard.
    """

    def __init__(self, total: int, profile_name: str):
        super().__init__()
        self.total = total
        self.profile_name = profile_name
        self.completed = 0
        self.failed = 0
        self.current_ticker: Optional[str] = None

    def update_progress(self, current_ticker: str, completed: int, failed: int) -> None:
        self.current_ticker = current_ticker
        self.completed = completed
        self.failed = failed

    def reset_for_next_stock(self) -> None:
        """Clear per-stock state when moving to the next ticker."""
        self.reset_per_stock()

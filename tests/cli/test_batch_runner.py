import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from cli.batch_runner import BatchRunner


@pytest.fixture(autouse=True)
def _mock_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_batch_runner_skips_completed(tmp_path):
    """If a ticker already has complete_report.md, skip it."""
    runner = BatchRunner(
        tickers=["AAPL"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=tmp_path / "reports",
    )
    # Simulate pre-existing report
    ticker_dir = runner.output_dir / "AAPL"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "complete_report.md").write_text("done")

    with patch.object(runner, "_run_single") as mock_run:
        runner.run()
        mock_run.assert_not_called()


def test_batch_runner_records_failure(tmp_path):
    """If _run_single raises, record failure and continue."""
    runner = BatchRunner(
        tickers=["AAPL", "MSFT"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=tmp_path / "reports",
    )

    def side_effect(ticker):
        if ticker == "AAPL":
            raise RuntimeError("API error")

    with patch.object(runner, "_run_single", side_effect=side_effect):
        runner.run()

    assert runner.failures == {"AAPL": "API error"}
    assert "AAPL" in runner.completed_tickers
    assert "MSFT" in runner.completed_tickers


def test_generate_summary_creates_markdown(tmp_path):
    runner = BatchRunner(
        tickers=["AAPL", "MSFT"],
        profile_config={"llm_provider": "openai", "output_language": "English"},
        output_dir=tmp_path / "reports",
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

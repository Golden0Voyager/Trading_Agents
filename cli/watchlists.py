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

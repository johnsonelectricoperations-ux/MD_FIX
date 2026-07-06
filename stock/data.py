"""Price data loading with local CSV caching.

Data providers (Yahoo Finance etc.) may be unreachable in some environments,
e.g. remote AI sessions with restricted networks. Therefore every download is
cached as CSV under the data directory, and backtests always read from the
cache. Run scripts/fetch_data.py on a machine with network access to refresh.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path("data")


def cache_path(ticker: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Return the CSV cache file path for a ticker."""
    return cache_dir / f"{ticker.replace('.', '_')}.csv"


def fetch_daily_closes(ticker: str, start: str = "2010-01-01") -> pd.Series:
    """Download daily adjusted closes from Yahoo Finance. Requires network."""
    import yfinance as yf  # lazy import: offline usage must not require it

    frame = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if frame is None or frame.empty:
        raise RuntimeError(f"no data returned for {ticker}")
    closes = frame["Close"]
    if isinstance(closes, pd.DataFrame):  # yfinance may return ticker-level columns
        closes = closes.iloc[:, 0]
    closes = closes.dropna()
    closes.name = ticker
    closes.index.name = "date"
    return closes


def save_to_cache(closes: pd.Series, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Write a close-price series to its CSV cache file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(str(closes.name), cache_dir)
    closes.to_csv(path, encoding="utf-8")
    return path


def load_from_cache(ticker: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> pd.Series:
    """Read a cached close-price series. Raises FileNotFoundError if absent."""
    path = cache_path(ticker, cache_dir)
    frame = pd.read_csv(path, index_col=0, parse_dates=True, encoding="utf-8")
    closes = frame.iloc[:, 0].astype(float)
    closes.name = ticker
    return closes


def load_price_table(tickers: list[str], cache_dir: Path = DEFAULT_CACHE_DIR) -> pd.DataFrame:
    """Load cached prices for several tickers, aligned on common trading days.

    Rows before all tickers have data are dropped so momentum lookbacks are
    computed on a complete panel (avoids fake signals from missing assets).
    """
    columns = [load_from_cache(t, cache_dir) for t in tickers]
    table = pd.concat(columns, axis=1).sort_index()
    return table.dropna(how="any")

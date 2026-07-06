"""Download and cache daily prices for the strategy universe.

Run this on a machine with internet access (your own PC):

    python scripts/fetch_data.py

Prices are cached as CSV under data/, which backtests read from.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock.config import UNIVERSE
from stock.data import DEFAULT_CACHE_DIR, fetch_daily_closes, save_to_cache

START_DATE = "2005-01-01"  # fetch as much history as each ETF has


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety (AGENTS.md §2)

    failures = 0
    for ticker, name in UNIVERSE.items():
        try:
            closes = fetch_daily_closes(ticker, start=START_DATE)
            path = save_to_cache(closes)
            first = closes.index[0].date()
            last = closes.index[-1].date()
            print(f"[성공] {name} ({ticker}): {len(closes)}일치 ({first} ~ {last}) -> {path}")
        except Exception as error:  # noqa: BLE001 - report per-ticker failure and continue
            failures += 1
            print(f"[실패] {name} ({ticker}): {error}")

    if failures:
        print(f"\n{failures}개 종목 다운로드 실패. 네트워크 연결을 확인한 뒤 다시 실행하세요.")
        return 1
    print(f"\n완료. 캐시 위치: {DEFAULT_CACHE_DIR.resolve()}")
    print("다음 단계: python scripts/run_backtest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

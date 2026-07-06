"""Inspect what the strategy actually held during one year, trade by trade.

Built to investigate the 2022 result (strategy lost as much as buy & hold in
the year it was supposed to defend). Prints every holding change plus a
monthly summary so whipsaw patterns become visible.

Usage:
    python scripts/diagnose.py 2022
    python scripts/diagnose.py 2026
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock.backtest import TRADE_EPSILON, run_backtest
from stock.config import CASH_ASSET, COST_RATE, REBALANCE_BAND, RISKY_ASSETS
from stock.data import load_from_cache, load_price_table
from stock.strategy import StrategyConfig, target_weights


def describe_holdings(row: pd.Series) -> str:
    parts = [
        f"{RISKY_ASSETS.get(ticker, ticker)} {weight:.0%}"
        for ticker, weight in row.items()
        if weight > TRADE_EPSILON
    ]
    return " + ".join(parts) if parts else "현금 100%"


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety (AGENTS.md §2)

    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2022

    try:
        prices = load_price_table(list(RISKY_ASSETS))
        cash_returns = load_from_cache(CASH_ASSET).pct_change().fillna(0.0)
    except FileNotFoundError as error:
        print("데이터 캐시가 없습니다:", error)
        print("인터넷이 되는 PC에서 먼저 실행하세요: python scripts/fetch_data.py")
        return 1

    weights = target_weights(prices, StrategyConfig())
    result = run_backtest(
        prices,
        weights,
        cost_rate=COST_RATE,
        cash_returns=cash_returns,
        rebalance_band=REBALANCE_BAND,
    )
    held = result.weights

    traded = held.diff().abs().sum(axis=1)
    if len(traded) > 0:
        traded.iloc[0] = held.iloc[0].abs().sum()
    change_days = held.index[traded > TRADE_EPSILON]
    changes_in_year = [day for day in change_days if day.year == year]

    print(f"=== {year}년 보유 변화 이력 ({len(changes_in_year)}회) ===")
    for day in changes_in_year:
        print(f"{day.date()}  -> {describe_holdings(held.loc[day])}")

    in_year = result.returns.index.year == year
    year_returns = result.returns[in_year]
    year_weights = held[in_year]
    benchmark = prices["069500.KS"].pct_change().fillna(0.0)[in_year]

    print()
    print(f"=== {year}년 월별 요약 ===")
    print("월    전략수익률   KODEX200   평균비중   주보유자산")
    for month, month_returns in year_returns.groupby(year_returns.index.month):
        month_mask = year_weights.index.month == month
        month_weights = year_weights[month_mask]
        exposure = float(month_weights.sum(axis=1).mean())
        average_weights = month_weights.mean()
        if float(average_weights.max()) > TRADE_EPSILON:
            main_asset = RISKY_ASSETS.get(str(average_weights.idxmax()), "?")
        else:
            main_asset = "현금"
        strategy_month = float((1.0 + month_returns).prod() - 1.0)
        bench_month = float((1.0 + benchmark[benchmark.index.month == month]).prod() - 1.0)
        print(
            f"{month:>2}월  {strategy_month:>9.2%}  {bench_month:>9.2%}  "
            f"{exposure:>7.0%}   {main_asset}"
        )

    total = float((1.0 + year_returns).prod() - 1.0)
    bench_total = float((1.0 + benchmark).prod() - 1.0)
    print()
    print(f"{year}년 합계: 전략 {total:.2%} / KODEX 200 {bench_total:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

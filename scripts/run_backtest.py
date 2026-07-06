"""Run the momentum-rotation backtest on cached data and print a Korean report.

Usage (after fetching data with scripts/fetch_data.py):

    python scripts/run_backtest.py            # main report + yearly breakdown
    python scripts/run_backtest.py --compare  # also compare config variants
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock.backtest import BacktestResult, run_backtest
from stock.config import CASH_ASSET, COST_RATE, REBALANCE_BAND, RISKY_ASSETS
from stock.data import load_from_cache, load_price_table
from stock.metrics import summarize
from stock.strategy import StrategyConfig, target_weights

# Variants for --compare. "구버전" replicates the pre-diagnosis strategy
# (no trend filter, no cooldown) so improvements are measured, not assumed.
COMPARE_VARIANTS: dict[str, tuple[StrategyConfig, float]] = {
    "기본 (추세필터+냉각 ON)": (StrategyConfig(), REBALANCE_BAND),
    "추세필터만 끔": (StrategyConfig(trend_filter_days=0), REBALANCE_BAND),
    "냉각기간만 끔": (StrategyConfig(crash_cooldown_days=0), REBALANCE_BAND),
    "구버전 (둘 다 끔)": (
        StrategyConfig(trend_filter_days=0, crash_cooldown_days=0),
        REBALANCE_BAND,
    ),
    "기본 + 변동성목표 20%": (StrategyConfig(vol_target=0.20), REBALANCE_BAND),
    "기본 + 변동성목표 25%": (StrategyConfig(vol_target=0.25), REBALANCE_BAND),
}


def print_row(label: str, stats: dict[str, float], extra: str = "") -> None:
    print(
        f"{label:<22} 연수익률 {stats['cagr']:>7.2%}   최대낙폭 {stats['max_drawdown']:>8.2%}   "
        f"변동성 {stats['volatility']:>7.2%}   샤프 {stats['sharpe']:>5.2f}   {extra}"
    )


def yearly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.year).prod() - 1.0


def print_yearly_table(result: BacktestResult, benchmark: pd.Series) -> None:
    strategy_years = yearly_returns(result.returns)
    benchmark_years = yearly_returns(benchmark.pct_change().fillna(0.0))
    print("연도별 수익률 (전략 vs KODEX 200 단순보유):")
    for year in strategy_years.index:
        bench = benchmark_years.get(year, float("nan"))
        print(f"  {year}   전략 {strategy_years[year]:>8.2%}   KODEX200 {bench:>8.2%}")


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety (AGENTS.md §2)

    try:
        prices = load_price_table(list(RISKY_ASSETS))
        cash_returns = load_from_cache(CASH_ASSET).pct_change().fillna(0.0)
    except FileNotFoundError as error:
        print("데이터 캐시가 없습니다:", error)
        print("인터넷이 되는 PC에서 먼저 실행하세요: python scripts/fetch_data.py")
        return 1

    config = StrategyConfig()
    weights = target_weights(prices, config)
    result = run_backtest(
        prices,
        weights,
        cost_rate=COST_RATE,
        cash_returns=cash_returns,
        rebalance_band=REBALANCE_BAND,
    )

    first = prices.index[0].date()
    last = prices.index[-1].date()
    average_exposure = float(result.weights.sum(axis=1).mean())
    print(f"백테스트 기간: {first} ~ {last} ({len(prices)} 거래일)")
    print(f"거래비용 가정: 편도 {COST_RATE:.3%} / 신호 다음 날 체결 (look-ahead 방지)")
    print(f"설정: 모멘텀 {config.lookbacks}일, 변동성 목표 {config.vol_target:.0%}, ")
    print(f"      급락 대피 {config.crash_window}일 내 -{config.crash_drawdown:.0%} ")
    print(f"      (대피 후 {config.crash_cooldown_days}일 재진입 금지), ")
    print(f"      추세 필터 {config.trend_filter_days}일 이평선, ")
    print(f"      리밸런싱 밴드 {REBALANCE_BAND:.0%}, 평균 주식 비중 {average_exposure:.0%}")
    print()
    print_row(
        "모멘텀 로테이션 전략",
        summarize(result.equity, result.returns),
        f"리밸런싱 {result.num_trade_days}회 / 비용 누계 {result.total_cost:.2%}",
    )
    for ticker, name in RISKY_ASSETS.items():
        held = prices[ticker] / prices[ticker].iloc[0]
        print_row(f"{name} 단순보유", summarize(held, held.pct_change().dropna()))
    print()
    print_yearly_table(result, prices["069500.KS"])

    if "--compare" in sys.argv:
        print()
        print("설정 비교 (같은 기간·같은 비용):")
        for label, (variant_config, band) in COMPARE_VARIANTS.items():
            variant_weights = target_weights(prices, variant_config)
            variant = run_backtest(
                prices,
                variant_weights,
                cost_rate=COST_RATE,
                cash_returns=cash_returns,
                rebalance_band=band,
            )
            print_row(
                f"  {label}",
                summarize(variant.equity, variant.returns),
                f"리밸런싱 {variant.num_trade_days}회",
            )

    print()
    print("주의: 과거 성과는 미래 수익을 보장하지 않습니다. 실거래 전 모의투자 검증 필수.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

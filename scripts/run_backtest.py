"""Run the momentum-rotation backtest on cached data and print a Korean report.

Usage (after fetching data with scripts/fetch_data.py):

    python scripts/run_backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock.backtest import run_backtest
from stock.data import load_from_cache, load_price_table
from stock.metrics import summarize
from stock.strategy import StrategyConfig, target_weights

# Keep in sync with scripts/fetch_data.py.
RISKY_ASSETS = {
    "069500.KS": "KODEX 200",
    "229200.KS": "KODEX 코스닥150",
    "360750.KS": "TIGER 미국S&P500",
}
CASH_ASSET = "153130.KS"  # KODEX money-market ETF
COST_RATE = 0.0005  # commission + slippage per side; KR ETFs have no transaction tax


def print_row(label: str, stats: dict[str, float], extra: str = "") -> None:
    print(
        f"{label:<22} 연수익률 {stats['cagr']:>7.2%}   최대낙폭 {stats['max_drawdown']:>8.2%}   "
        f"변동성 {stats['volatility']:>7.2%}   샤프 {stats['sharpe']:>5.2f}   {extra}"
    )


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
    result = run_backtest(prices, weights, cost_rate=COST_RATE, cash_returns=cash_returns)

    first = prices.index[0].date()
    last = prices.index[-1].date()
    print(f"백테스트 기간: {first} ~ {last} ({len(prices)} 거래일)")
    print(f"거래비용 가정: 편도 {COST_RATE:.3%} / 신호 다음 날 체결 (look-ahead 방지)")
    print(f"설정: 모멘텀 {config.lookbacks}일, 변동성 목표 {config.vol_target:.0%}, ")
    print(f"      급락 대피 {config.crash_window}일 내 -{config.crash_drawdown:.0%}")
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
    print("주의: 과거 성과는 미래 수익을 보장하지 않습니다. 실거래 전 모의투자 검증 필수.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

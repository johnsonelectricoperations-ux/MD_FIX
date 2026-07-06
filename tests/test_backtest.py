import math

import pandas as pd

from stock.backtest import run_backtest


def flat_then_spike_prices(days: int = 10, spike: float = 0.20) -> pd.DataFrame:
    index = pd.bdate_range("2024-01-01", periods=days)
    values = [100.0] * (days - 1) + [100.0 * (1.0 + spike)]
    return pd.DataFrame({"A": values}, index=index)


def test_no_look_ahead_spike_is_not_captured():
    # Weight goes to 1.0 only on the spike day itself. With 1-day execution
    # delay the spike must NOT be earned; equity stays flat (minus no costs,
    # since the buy would only execute after the data ends).
    prices = flat_then_spike_prices()
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights.iloc[-1] = 1.0
    result = run_backtest(prices, weights, cost_rate=0.0)
    assert math.isclose(float(result.equity.iloc[-1]), 1.0, rel_tol=1e-12)


def test_full_weight_from_start_captures_spike_minus_cost():
    prices = flat_then_spike_prices(spike=0.20)
    weights = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)
    cost_rate = 0.001
    result = run_backtest(prices, weights, cost_rate=cost_rate)
    # One initial buy (cost once), then the +20% on the last day is captured.
    expected = (1.0 - cost_rate) * 1.20
    assert math.isclose(float(result.equity.iloc[-1]), expected, rel_tol=1e-9)
    assert result.num_trade_days == 1


def test_constant_weights_trade_only_once():
    prices = flat_then_spike_prices()
    weights = pd.DataFrame(0.5, index=prices.index, columns=prices.columns)
    result = run_backtest(prices, weights, cost_rate=0.001)
    assert result.num_trade_days == 1
    assert math.isclose(result.turnover, 0.5, rel_tol=1e-12)


def test_rebalance_band_suppresses_daily_jitter():
    # Target weight wiggles ±2% around 0.5 every day; with a 10%p band the
    # portfolio should trade once at the start and then hold still.
    days = 30
    index = pd.bdate_range("2024-01-01", periods=days)
    prices = pd.DataFrame({"A": [100.0 + i for i in range(days)]}, index=index)
    jitter = [0.5 + (0.02 if i % 2 == 0 else -0.02) for i in range(days)]
    weights = pd.DataFrame({"A": jitter}, index=index)
    result = run_backtest(prices, weights, cost_rate=0.001, rebalance_band=0.10)
    assert result.num_trade_days == 1


def test_rebalance_band_never_blocks_an_asset_switch():
    # Rotation from A to B must execute even if the weight sizes are small.
    days = 10
    index = pd.bdate_range("2024-01-01", periods=days)
    prices = pd.DataFrame({"A": [100.0] * days, "B": [100.0] * days}, index=index)
    weights = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    weights.loc[index[:5], "A"] = 0.05
    weights.loc[index[5:], "B"] = 0.05
    result = run_backtest(prices, weights, cost_rate=0.0, rebalance_band=0.10)
    # Held weights lag by one day: B must be held from day 7 onward.
    assert float(result.weights["B"].iloc[-1]) == 0.05
    assert float(result.weights["A"].iloc[-1]) == 0.0


def test_cash_remainder_earns_cash_returns():
    days = 10
    index = pd.bdate_range("2024-01-01", periods=days)
    prices = pd.DataFrame({"A": [100.0] * days}, index=index)
    weights = pd.DataFrame(0.0, index=index, columns=["A"])  # always 100% cash
    cash_returns = pd.Series(0.0001, index=index)  # ~2.5%/yr money market
    result = run_backtest(prices, weights, cost_rate=0.0, cash_returns=cash_returns)
    # Delay leaves day 1 at weight 0 too, but cash weight is 1.0 every day.
    expected = (1.0 + 0.0001) ** days
    assert math.isclose(float(result.equity.iloc[-1]), expected, rel_tol=1e-9)

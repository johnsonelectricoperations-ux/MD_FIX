import numpy as np
import pandas as pd

from stock.strategy import StrategyConfig, target_weights

CONFIG = StrategyConfig(lookbacks=(20, 40), vol_window=10, crash_window=10, crash_drawdown=0.10)


def make_prices(days: int, daily_returns: dict[str, float]) -> pd.DataFrame:
    """Deterministic geometric price paths, one column per asset."""
    index = pd.bdate_range("2024-01-01", periods=days)
    data = {
        name: 100.0 * np.cumprod(np.full(days, 1.0 + ret)) for name, ret in daily_returns.items()
    }
    return pd.DataFrame(data, index=index)


def test_selects_the_uptrending_asset_only():
    prices = make_prices(120, {"UP": 0.002, "DOWN": -0.002})
    weights = target_weights(prices, CONFIG)
    assert weights["DOWN"].max() == 0.0
    assert weights["UP"].iloc[-1] > 0.0


def test_goes_to_cash_when_everything_falls():
    prices = make_prices(120, {"A": -0.001, "B": -0.003})
    weights = target_weights(prices, CONFIG)
    assert float(weights.sum().sum()) == 0.0


def test_volatility_targeting_caps_position_size():
    # Alternating +4%/-3.5% is wildly volatile; annualized vol far above target
    days = 120
    index = pd.bdate_range("2024-01-01", periods=days)
    swings = np.array([1.04 if i % 2 == 0 else 0.965 for i in range(days)])
    prices = pd.DataFrame({"WILD": 100.0 * np.cumprod(swings)}, index=index)
    weights = target_weights(prices, CONFIG)
    positive = weights["WILD"][weights["WILD"] > 0]
    assert len(positive) > 0
    assert positive.max() < 0.5  # vol targeting must have shrunk the position


def test_crash_circuit_breaker_forces_cash():
    # Long uptrend, then a 3-day crash of ~15%: momentum lookbacks (20/40d)
    # still look positive, so only the circuit breaker can force cash.
    up = [1.003] * 100
    crash = [0.95, 0.95, 0.95]
    factors = np.array(up + crash)
    index = pd.bdate_range("2024-01-01", periods=len(factors))
    prices = pd.DataFrame({"X": 100.0 * np.cumprod(factors)}, index=index)

    weights = target_weights(prices, CONFIG)
    assert weights["X"].iloc[99] > 0.0  # invested during the uptrend
    assert weights["X"].iloc[-1] == 0.0  # in cash after the crash

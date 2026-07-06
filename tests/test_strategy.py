import numpy as np
import pandas as pd

from stock.strategy import StrategyConfig, target_weights

# Baseline config with the newer layers (trend filter, cooldown, entry
# hysteresis) disabled so each test exercises exactly one mechanism.
CONFIG = StrategyConfig(
    lookbacks=(20, 40),
    vol_window=10,
    crash_window=10,
    crash_drawdown=0.10,
    crash_cooldown_days=0,
    trend_filter_days=0,
    entry_threshold=0.0,
)


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


def test_trend_filter_blocks_asset_below_moving_average():
    # Rise, then an -8% gap (too small for the crash breaker) followed by a
    # slow drift: short momentum turns positive again, but price stays below
    # the 50-day average. Only the trend filter can keep the strategy out.
    up = [1.003] * 100
    gap = [0.92]
    drift = [1.0002] * 29
    factors = np.array(up + gap + drift)
    index = pd.bdate_range("2024-01-01", periods=len(factors))
    prices = pd.DataFrame({"X": 100.0 * np.cumprod(factors)}, index=index)

    base = StrategyConfig(
        lookbacks=(5, 10),
        vol_window=10,
        crash_window=10,
        crash_drawdown=0.10,
        crash_cooldown_days=0,
        trend_filter_days=0,
        entry_threshold=0.0,
    )
    with_filter = StrategyConfig(
        lookbacks=(5, 10),
        vol_window=10,
        crash_window=10,
        crash_drawdown=0.10,
        crash_cooldown_days=0,
        trend_filter_days=50,
        entry_threshold=0.0,
    )
    tail = slice(115, 130)
    assert target_weights(prices, base)["X"].iloc[tail].max() > 0.0
    assert target_weights(prices, with_filter)["X"].iloc[tail].max() == 0.0


def test_crash_cooldown_delays_re_entry():
    # Uptrend, a -12% crash day, then a steady rebound. Without a cooldown the
    # decayed rolling high lets the strategy re-enter within days; with a
    # 15-day cooldown it must stay out, then come back.
    up = [1.003] * 60
    crash = [0.88]
    rebound = [1.01] * 40
    factors = np.array(up + crash + rebound)
    index = pd.bdate_range("2024-01-01", periods=len(factors))
    prices = pd.DataFrame({"X": 100.0 * np.cumprod(factors)}, index=index)

    def config(cooldown: int) -> StrategyConfig:
        return StrategyConfig(
            lookbacks=(5, 10),
            vol_window=10,
            crash_window=10,
            crash_drawdown=0.10,
            crash_cooldown_days=cooldown,
            trend_filter_days=0,
            entry_threshold=0.0,
        )

    without = target_weights(prices, config(0))["X"]
    with_cooldown = target_weights(prices, config(15))["X"]
    churn_window = slice(63, 75)
    assert without.iloc[churn_window].max() > 0.0  # quick re-entry (the bug)
    assert with_cooldown.iloc[churn_window].max() == 0.0  # cooldown holds
    assert with_cooldown.iloc[85:].max() > 0.0  # but re-entry does happen


def test_falls_back_to_second_best_asset_when_best_is_crashing():
    # A has the higher momentum thanks to a long run-up but is crashing right
    # now; B trends up quietly. The strategy must rotate into B, not cash.
    a_factors = np.array([1.01] * 90 + [0.94] * 3)
    b_factors = np.array([1.002] * 93)
    index = pd.bdate_range("2024-01-01", periods=93)
    prices = pd.DataFrame(
        {"A": 100.0 * np.cumprod(a_factors), "B": 100.0 * np.cumprod(b_factors)},
        index=index,
    )
    weights = target_weights(prices, CONFIG)
    assert weights["A"].iloc[-1] == 0.0
    assert weights["B"].iloc[-1] > 0.0


def hysteresis_config(threshold: float) -> StrategyConfig:
    return StrategyConfig(
        lookbacks=(20, 40),
        vol_window=10,
        crash_window=10,
        crash_drawdown=0.10,
        crash_cooldown_days=0,
        trend_filter_days=0,
        entry_threshold=threshold,
    )


def test_entry_threshold_blocks_weak_new_positions():
    # Flat, then a feeble +0.05%/day drift: momentum is barely positive
    # (~1.5% at best), which is exactly the zero-hover regime that caused
    # daily in/out churn in 2022. A 2% entry threshold must never enter.
    factors = np.array([1.0] * 60 + [1.0005] * 60)
    index = pd.bdate_range("2024-01-01", periods=len(factors))
    prices = pd.DataFrame({"X": 100.0 * np.cumprod(factors)}, index=index)

    assert target_weights(prices, hysteresis_config(0.0))["X"].max() > 0.0
    assert target_weights(prices, hysteresis_config(0.02))["X"].max() == 0.0


def test_incumbent_survives_momentum_fade_below_entry_threshold():
    # Strong rise (enters well above the threshold), then a slow crawl that
    # decays momentum to ~0.6%: below the entry threshold but still positive,
    # so the position must be KEPT, not churned out.
    factors = np.array([1.005] * 60 + [1.0002] * 60)
    index = pd.bdate_range("2024-01-01", periods=len(factors))
    prices = pd.DataFrame({"X": 100.0 * np.cumprod(factors)}, index=index)

    weights = target_weights(prices, hysteresis_config(0.02))["X"]
    assert weights.iloc[45:].min() > 0.0  # held continuously once entered


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

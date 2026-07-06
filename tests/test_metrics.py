import math

import pandas as pd

from stock.metrics import cagr, max_drawdown, sharpe_ratio

TRADING_DAYS_PER_YEAR = 252


def test_cagr_of_flat_curve_is_zero():
    equity = pd.Series([1.0] * 100)
    assert cagr(equity) == 0.0


def test_cagr_doubling_in_one_year():
    equity = pd.Series([1.0 + i * (1.0 / TRADING_DAYS_PER_YEAR) for i in range(253)])
    # Ends at 2.0 after exactly 252 daily steps -> CAGR should be 100%
    assert math.isclose(cagr(equity), 1.0, rel_tol=1e-9)


def test_max_drawdown_simple_case():
    equity = pd.Series([1.0, 1.5, 0.75, 1.2])
    # Peak 1.5 -> trough 0.75 is a 50% drawdown
    assert math.isclose(max_drawdown(equity), -0.5, rel_tol=1e-9)


def test_max_drawdown_monotonic_up_is_zero():
    equity = pd.Series([1.0, 1.1, 1.2, 1.3])
    assert max_drawdown(equity) == 0.0


def test_sharpe_zero_when_no_volatility():
    returns = pd.Series([0.0] * 50)
    assert sharpe_ratio(returns) == 0.0

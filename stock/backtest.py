"""Backtest engine: applies target weights to prices with costs and no look-ahead.

Anti-look-ahead contract: `weights` passed in are decided on day t's close.
The engine shifts them by `delay` days (default 1), so a decision made on
day t only earns day t+1's return. Tested in tests/test_backtest.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TRADE_EPSILON = 1e-9


def apply_rebalance_band(weights: pd.DataFrame, band: float) -> pd.DataFrame:
    """Suppress small daily weight adjustments to cut trading frequency.

    The volatility-targeting layer nudges target weights a little every day,
    which would trigger a tiny order almost daily. This keeps the previously
    executed weights until the target drifts more than `band` in total, or an
    asset enters/leaves the portfolio (a switch always trades immediately).
    """
    if band <= 0:
        return weights
    executed = weights.copy()
    previous = executed.iloc[0]
    for i in range(1, len(executed)):
        target = executed.iloc[i]
        switched = bool(((target > 0) != (previous > 0)).any())
        if not switched and float((target - previous).abs().sum()) <= band:
            executed.iloc[i] = previous
        else:
            previous = target
    return executed


@dataclass
class BacktestResult:
    equity: pd.Series  # cumulative growth of 1.0
    returns: pd.Series  # daily net returns
    weights: pd.DataFrame  # weights as actually held (after execution delay)
    turnover: float  # sum of |weight changes| over the whole period
    total_cost: float  # cumulative cost drag (fraction of equity, approx)
    num_trade_days: int  # number of days on which any rebalancing happened


def run_backtest(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    cost_rate: float = 0.0005,
    delay: int = 1,
    cash_returns: pd.Series | None = None,
    rebalance_band: float = 0.0,
) -> BacktestResult:
    """Simulate the portfolio.

    cost_rate is charged per unit of weight traded (one-way). Korean equity
    ETFs are exempt from the securities transaction tax, so 0.0005 (0.05%)
    approximates commission plus slippage; adjust when brokerage is decided.
    cash_returns, if given (e.g. a money-market ETF), is earned on the
    uninvested remainder; otherwise cash earns 0%. rebalance_band > 0
    suppresses small daily weight adjustments (see apply_rebalance_band).
    """
    asset_returns = prices.pct_change().fillna(0.0)
    aligned = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    held = apply_rebalance_band(aligned, rebalance_band).shift(delay).fillna(0.0)
    gross = (held * asset_returns).sum(axis=1)
    if cash_returns is not None:
        cash_weight = (1.0 - held.sum(axis=1)).clip(lower=0.0)
        gross = gross + cash_weight * cash_returns.reindex(prices.index).fillna(0.0)

    traded = held.diff().abs().sum(axis=1)
    if len(traded) > 0:
        traded.iloc[0] = held.iloc[0].abs().sum()
    costs = traded * cost_rate
    net = gross - costs
    equity = (1.0 + net).cumprod()
    return BacktestResult(
        equity=equity,
        returns=net,
        weights=held,
        turnover=float(traded.sum()),
        total_cost=float(costs.sum()),
        num_trade_days=int((traded > TRADE_EPSILON).sum()),
    )

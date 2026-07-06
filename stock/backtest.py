"""Backtest engine: applies target weights to prices with costs and no look-ahead.

Anti-look-ahead contract: `weights` passed in are decided on day t's close.
The engine shifts them by `delay` days (default 1), so a decision made on
day t only earns day t+1's return. Tested in tests/test_backtest.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TRADE_EPSILON = 1e-9


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
) -> BacktestResult:
    """Simulate the portfolio.

    cost_rate is charged per unit of weight traded (one-way). Korean equity
    ETFs are exempt from the securities transaction tax, so 0.0005 (0.05%)
    approximates commission plus slippage; adjust when brokerage is decided.
    cash_returns, if given (e.g. a money-market ETF), is earned on the
    uninvested remainder; otherwise cash earns 0%.
    """
    asset_returns = prices.pct_change().fillna(0.0)
    held = (
        weights.reindex(index=prices.index, columns=prices.columns)
        .fillna(0.0)
        .shift(delay)
        .fillna(0.0)
    )
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

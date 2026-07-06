"""Performance metrics for backtest results."""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def cagr(equity: pd.Series) -> float:
    """Compound annual growth rate of an equity curve starting at 1.0."""
    if len(equity) < 2:
        return 0.0
    years = (len(equity) - 1) / TRADING_DAYS_PER_YEAR
    final = float(equity.iloc[-1])
    if years <= 0 or final <= 0:
        return 0.0
    return final ** (1.0 / years) - 1.0


def max_drawdown(equity: pd.Series) -> float:
    """Worst peak-to-trough decline, as a negative fraction (e.g. -0.35)."""
    if len(equity) == 0:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def annualized_volatility(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    return float(returns.std() * math.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe_ratio(returns: pd.Series, risk_free_annual: float = 0.0) -> float:
    vol = annualized_volatility(returns)
    if vol == 0:
        return 0.0
    excess = float(returns.mean()) * TRADING_DAYS_PER_YEAR - risk_free_annual
    return excess / vol


def summarize(equity: pd.Series, returns: pd.Series) -> dict[str, float]:
    return {
        "cagr": cagr(equity),
        "max_drawdown": max_drawdown(equity),
        "volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "final_equity": float(equity.iloc[-1]) if len(equity) else 1.0,
    }

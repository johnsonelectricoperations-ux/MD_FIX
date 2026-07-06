"""ETF momentum rotation with risk-control layers (see docs/DECISIONS.md D-006).

Three layers, evaluated daily on close prices:
1. Momentum selection: hold the single asset with the best average momentum
   over the configured lookbacks; if the best score is not positive, hold cash
   (absolute momentum filter).
2. Volatility targeting: scale the position down when recent realized
   volatility exceeds the target, so position size shrinks in wild markets.
3. Crash circuit breaker: if the selected asset has fallen more than the
   threshold from its recent high, go to cash regardless of momentum. This is
   the fast layer for events like the 2026-06 KOSPI single-day -10% crash,
   which slow momentum lookbacks cannot react to.

Weights produced here are DECIDED on day t's close. The backtest engine is
responsible for applying them with a delay (executed at the next close) so
there is no look-ahead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class StrategyConfig:
    """Tunable parameters. Defaults are a starting point, not optimized."""

    lookbacks: tuple[int, ...] = (63, 126)  # ~3 and ~6 months, in trading days
    absolute_filter: bool = True  # go to cash when best momentum <= 0
    vol_target: float = 0.15  # annualized volatility target (layer 2)
    vol_window: int = 20  # days used to estimate realized volatility
    crash_window: int = 10  # days of recent high for the circuit breaker
    crash_drawdown: float = 0.10  # 10% drop from recent high -> cash (layer 3)


def momentum_scores(prices: pd.DataFrame, lookbacks: tuple[int, ...]) -> pd.DataFrame:
    """Average of simple returns over each lookback period, per asset."""
    parts = [prices / prices.shift(lb) - 1.0 for lb in lookbacks]
    return sum(parts) / len(parts)


def target_weights(prices: pd.DataFrame, cfg: StrategyConfig | None = None) -> pd.DataFrame:
    """Compute daily target weights for risky assets; the remainder is cash.

    Rows are all zero (100% cash) until every lookback has enough history.
    """
    cfg = cfg or StrategyConfig()
    scores = momentum_scores(prices, cfg.lookbacks)
    daily_returns = prices.pct_change()
    realized_vol = daily_returns.rolling(cfg.vol_window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)
    recent_high = prices.rolling(cfg.crash_window).max()
    drawdown = prices / recent_high - 1.0

    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    warm_days = scores.dropna(how="any").index
    for day in warm_days:
        row = scores.loc[day]
        best = row.idxmax()
        if cfg.absolute_filter and row[best] <= 0:
            continue  # layer 1: nothing is trending up -> cash
        if drawdown.loc[day, best] <= -cfg.crash_drawdown:
            continue  # layer 3: selected asset is crashing -> cash
        vol = realized_vol.loc[day, best]
        if pd.isna(vol) or vol <= 0:
            weight = 1.0
        else:
            weight = min(1.0, cfg.vol_target / vol)  # layer 2
        weights.loc[day, best] = weight
    return weights

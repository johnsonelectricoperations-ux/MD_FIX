"""ETF momentum rotation with risk-control layers (see docs/DECISIONS.md D-006).

Layers, evaluated daily on close prices. Candidates are tried in momentum
order (best first); the first one passing every gate is held:
1. Momentum selection: rank assets by average momentum over the configured
   lookbacks. If even the best score is not positive, hold cash (absolute
   momentum filter).
2. Trend regime filter: an asset trading below its long moving average is
   ineligible no matter how its momentum ranks. Added after the 2022
   diagnosis: bear-market rallies kept re-selecting the "least bad" asset.
3. Crash circuit breaker: any asset that has fallen more than the threshold
   from its recent high is blocked for a cooldown period, whether or not it
   was being held. The cooldown exists because the rolling-high reference
   decays within days, which caused daily exit/re-enter churn in the 2022
   backtest.
4. Volatility targeting: scale the chosen position down when recent realized
   volatility exceeds the target.

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
    vol_target: float = 0.15  # annualized volatility target (layer 4)
    vol_window: int = 20  # days used to estimate realized volatility
    crash_window: int = 10  # days of recent high for the circuit breaker
    crash_drawdown: float = 0.10  # 10% drop from recent high -> skip asset (layer 3)
    crash_cooldown_days: int = 15  # re-entry ban after a crash exit; 0 disables
    trend_filter_days: int = 200  # asset must trade above this SMA; 0 disables


def momentum_scores(prices: pd.DataFrame, lookbacks: tuple[int, ...]) -> pd.DataFrame:
    """Average of simple returns over each lookback period, per asset."""
    parts = [prices / prices.shift(lb) - 1.0 for lb in lookbacks]
    return sum(parts) / len(parts)


def target_weights(prices: pd.DataFrame, cfg: StrategyConfig | None = None) -> pd.DataFrame:
    """Compute daily target weights for risky assets; the remainder is cash.

    Rows are all zero (100% cash) until every momentum lookback has enough
    history. The trend filter needs `trend_filter_days` of history per asset
    before that asset becomes eligible, which extends the warmup.
    """
    cfg = cfg or StrategyConfig()
    scores = momentum_scores(prices, cfg.lookbacks)
    daily_returns = prices.pct_change()
    realized_vol = daily_returns.rolling(cfg.vol_window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)
    recent_high = prices.rolling(cfg.crash_window).max()
    drawdown = prices / recent_high - 1.0
    trend_sma = prices.rolling(cfg.trend_filter_days).mean() if cfg.trend_filter_days > 0 else None

    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    blocked_until: dict[str, int] = {}  # asset -> last row index of its cooldown
    for i in range(len(prices)):
        # Layer 3 trigger runs for every asset (held or not) BEFORE selection:
        # an exit via the momentum filter must not bypass the cooldown.
        crashing = drawdown.iloc[i] <= -cfg.crash_drawdown
        for asset in prices.columns[crashing.fillna(False)]:
            blocked_until[asset] = i + cfg.crash_cooldown_days
        row = scores.iloc[i]
        if row.isna().any():
            continue  # momentum warmup
        for asset in row.sort_values(ascending=False).index:
            if cfg.absolute_filter and row[asset] <= 0:
                break  # layer 1: nothing left is trending up -> cash
            if trend_sma is not None:
                sma = trend_sma.iloc[i][asset]
                if pd.isna(sma) or prices.iloc[i][asset] <= sma:
                    continue  # layer 2: below long-term trend -> ineligible
            if blocked_until.get(asset, -1) >= i:
                continue  # layer 3: crashing now or cooling down -> ineligible
            vol = realized_vol.iloc[i][asset]
            if pd.isna(vol) or vol <= 0:
                weight = 1.0
            else:
                weight = min(1.0, cfg.vol_target / vol)  # layer 4
            weights.iloc[i, weights.columns.get_loc(asset)] = weight
            break  # hold exactly one asset
    return weights

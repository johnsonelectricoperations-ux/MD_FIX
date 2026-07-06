"""Shared universe and trading assumptions used by all scripts.

Single source of truth so fetch/backtest/diagnose scripts cannot drift apart.
"""

from __future__ import annotations

RISKY_ASSETS: dict[str, str] = {
    "069500.KS": "KODEX 200",
    "229200.KS": "KODEX 코스닥150",
    "360750.KS": "TIGER 미국S&P500",
}
CASH_ASSET = "153130.KS"
CASH_NAME = "KODEX 단기채권(현금)"
UNIVERSE: dict[str, str] = {**RISKY_ASSETS, CASH_ASSET: CASH_NAME}

COST_RATE = 0.0005  # commission + slippage per side; KR ETFs have no transaction tax
REBALANCE_BAND = 0.10  # skip re-orders until target weight drifts >10%p total

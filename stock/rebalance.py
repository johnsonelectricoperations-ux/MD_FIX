"""Convert strategy target weights into executable share orders.

Money arithmetic uses Decimal and integer KRW prices (AGENTS.md §5-6).
Mirrors the backtest's rebalance band: if the asset set is unchanged and the
total weight drift is within the band, no orders are produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

CASH_BUFFER = Decimal("0.01")  # keep 1% uninvested to absorb market-order slippage


@dataclass(frozen=True)
class Order:
    code: str  # 6-digit KRX code
    side: str  # "buy" or "sell"
    quantity: int


def compute_orders(
    targets: dict[str, float],
    holdings: dict[str, int],
    prices: dict[str, int],
    cash: Decimal,
    band: float = 0.10,
) -> list[Order]:
    """Return sell orders first, then buy orders sized to the available cash.

    targets: weight per code (0..1, summing to <= 1; the remainder stays as
    deposit). Codes missing from `targets` but present in `holdings` are
    treated as target 0 and sold.
    """
    codes = sorted(set(targets) | set(holdings))
    total = cash + sum(Decimal(holdings.get(c, 0)) * Decimal(prices[c]) for c in codes)
    if total <= 0:
        return []

    target_by_code = {c: Decimal(str(targets.get(c, 0.0))) for c in codes}
    current_by_code = {c: Decimal(holdings.get(c, 0)) * Decimal(prices[c]) / total for c in codes}

    held_set = {c for c in codes if holdings.get(c, 0) > 0}
    target_set = {c for c in codes if target_by_code[c] > 0}
    drift = sum(abs(target_by_code[c] - current_by_code[c]) for c in codes)
    if held_set == target_set and drift <= Decimal(str(band)):
        return []  # within the rebalance band: hold still (D-008)

    desired_qty: dict[str, int] = {}
    investable = total * (Decimal(1) - CASH_BUFFER)
    for code in codes:
        amount = target_by_code[code] * investable
        desired_qty[code] = int((amount / Decimal(prices[code])).to_integral_value(ROUND_FLOOR))

    sells: list[Order] = []
    buys: list[tuple[str, int]] = []
    for code in codes:
        delta = desired_qty[code] - holdings.get(code, 0)
        if target_by_code[code] == 0 and holdings.get(code, 0) > 0:
            sells.append(Order(code, "sell", holdings[code]))  # full exit
        elif delta < 0:
            sells.append(Order(code, "sell", -delta))
        elif delta > 0:
            buys.append((code, delta))

    # Size buys against deposit plus estimated sell proceeds, never beyond.
    budget = cash + sum(Decimal(o.quantity) * Decimal(prices[o.code]) for o in sells)
    orders = list(sells)
    for code, wanted in buys:
        price = Decimal(prices[code])
        affordable = int((budget / price).to_integral_value(ROUND_FLOOR))
        quantity = min(wanted, affordable)
        if quantity > 0:
            orders.append(Order(code, "buy", quantity))
            budget -= Decimal(quantity) * price
    return orders

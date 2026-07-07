"""Live-trading guardrails mandated by AGENTS.md §5.

Two independent layers, both applied to BUY orders only — sell orders are
never blocked, because in a disaster the protective exit to cash must always
remain possible (a runaway sell is naturally bounded by what the account
holds, a runaway buy is not):

1. Per-order value cap (MAX_ORDER_VALUE_KRW): a buy larger than this is
   almost certainly a calculation or balance-parsing error, not a signal.
2. Daily loss kill switch (DAILY_LOSS_LIMIT_PCT): if the account value fell
   more than this fraction since the previous run, stop opening positions
   and alert; something is wrong with the market or with us.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from stock.rebalance import Order

KST = ZoneInfo("Asia/Seoul")
DEFAULT_MAX_ORDER_VALUE = Decimal("6000000")  # sized for <=5M KRW capital (D-013)
DEFAULT_DAILY_LOSS_LIMIT = Decimal("0.15")
DEFAULT_STATE_FILE = Path("data/account_state.json")


def max_order_value_from_env() -> Decimal:
    raw = os.environ.get("MAX_ORDER_VALUE_KRW")
    return Decimal(raw) if raw else DEFAULT_MAX_ORDER_VALUE


def daily_loss_limit_from_env() -> Decimal:
    raw = os.environ.get("DAILY_LOSS_LIMIT_PCT")
    return Decimal(raw) / 100 if raw else DEFAULT_DAILY_LOSS_LIMIT


def cap_buy_orders(
    orders: list[Order], prices: dict[str, int], max_value: Decimal
) -> tuple[list[Order], list[str]]:
    """Drop buys whose value exceeds the cap; return kept orders and notes."""
    kept: list[Order] = []
    notes: list[str] = []
    for order in orders:
        value = Decimal(order.quantity) * Decimal(prices[order.code])
        if order.side == "buy" and value > max_value:
            notes.append(
                f"[한도차단] 매수 {order.code} x {order.quantity}주"
                f" ({value:,.0f}원 > 한도 {max_value:,.0f}원) — 주문 제외"
            )
        else:
            kept.append(order)
    return kept, notes


def kill_switch_triggered(
    total_value: Decimal,
    limit: Decimal,
    state_file: Path = DEFAULT_STATE_FILE,
) -> str | None:
    """Return a warning message if the account fell past the loss limit."""
    if not state_file.exists():
        return None
    previous = json.loads(state_file.read_text(encoding="utf-8"))
    previous_value = Decimal(previous["total_value"])
    if previous_value <= 0:
        return None
    drop = (previous_value - total_value) / previous_value
    if drop >= limit:
        return (
            f"[킬스위치] 계좌 평가액이 지난 실행({previous['date']}) 대비"
            f" {drop:.1%} 하락 (한도 {limit:.0%}) — 신규 매수를 차단합니다."
            f" 원인 확인 후 data/account_state.json을 갱신하면 해제됩니다."
        )
    return None


def record_account_state(total_value: Decimal, state_file: Path = DEFAULT_STATE_FILE) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "date": datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M"),
        "total_value": str(total_value),
    }
    state_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

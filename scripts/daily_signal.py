"""Daily job: refresh data, compute today's target allocation, and (optionally)
rebalance the KIS account with market orders. Designed to run just before the
closing auction, 15:15-15:20 KST (docs/ROADMAP.md operating procedure).

Usage:
    python scripts/daily_signal.py                 # signal + planned orders only
    python scripts/daily_signal.py --execute       # place orders (paper mode)
    python scripts/daily_signal.py --execute --live  # live orders (KIS_MODE=live too)
    python scripts/daily_signal.py --no-fetch      # skip the data refresh

Safety (AGENTS.md §5): without --execute nothing is ordered. Live trading
requires BOTH the --live flag and KIS_MODE=live in .env; paper is the default.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from stock.config import CASH_ASSET, REBALANCE_BAND, RISKY_ASSETS, UNIVERSE
from stock.data import fetch_daily_closes, load_price_table, save_to_cache
from stock.kis import Balance, KISClient, KISConfig, KISError
from stock.notify import send_telegram
from stock.rebalance import Order, compute_orders
from stock.strategy import StrategyConfig, target_weights

KST = ZoneInfo("Asia/Seoul")


def kis_code(ticker: str) -> str:
    """'069500.KS' -> '069500' (KIS uses bare 6-digit codes)."""
    return ticker.split(".")[0]


def refresh_data(lines: list[str]) -> None:
    for ticker in UNIVERSE:
        try:
            save_to_cache(fetch_daily_closes(ticker, start="2015-01-01"))
        except Exception as error:  # noqa: BLE001 - stale cache is better than no run
            lines.append(f"[경고] {ticker} 시세 갱신 실패, 캐시 사용: {error}")


def compute_targets(lines: list[str]) -> dict[str, float]:
    """Today's target weights keyed by 6-digit code, cash ETF included."""
    try:
        prices = load_price_table(list(RISKY_ASSETS))
    except FileNotFoundError as error:
        raise RuntimeError(
            f"데이터 캐시가 없습니다({error}). 먼저 실행: python scripts/fetch_data.py"
        ) from error
    weights = target_weights(prices, StrategyConfig()).iloc[-1]
    as_of = prices.index[-1].date()
    lines.append(f"기준 데이터: {as_of} 종가까지")
    targets = {kis_code(t): float(w) for t, w in weights.items()}
    targets[kis_code(CASH_ASSET)] = max(0.0, 1.0 - sum(targets.values()))
    for ticker, name in UNIVERSE.items():
        weight = targets.get(kis_code(ticker), 0.0)
        lines.append(f"  {name}: {weight:.0%}")
    return targets


def plan_orders(
    client: KISClient, targets: dict[str, float], lines: list[str]
) -> tuple[list[Order], Balance, dict[str, int]]:
    balance = client.get_balance()
    prices = {code: client.get_price(code) for code in set(targets) | set(balance.holdings)}
    lines.append(f"계좌: 총평가 {balance.total_value:,.0f}원 / 예수금 {balance.cash:,.0f}원")
    orders = compute_orders(targets, balance.holdings, prices, balance.cash, band=REBALANCE_BAND)
    if not orders:
        lines.append("주문 없음 (목표 비중과의 차이가 밴드 이내)")
    for order in orders:
        side = "매수" if order.side == "buy" else "매도"
        lines.append(f"  [{side}] {order.code} x {order.quantity}주 (시장가)")
    return orders, balance, prices


def execute_orders(client: KISClient, orders: list[Order], lines: list[str]) -> None:
    for order in orders:
        side = "매수" if order.side == "buy" else "매도"
        try:
            order_no = client.place_market_order(order.code, order.quantity, order.side)
            lines.append(
                f"  [체결접수] {side} {order.code} x {order.quantity} (주문번호 {order_no})"
            )
        except KISError as error:
            lines.append(f"  [주문실패] {side} {order.code} x {order.quantity}: {error}")


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety (AGENTS.md §2)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    execute = "--execute" in sys.argv
    live_flag = "--live" in sys.argv
    now = datetime.now(tz=KST)
    lines: list[str] = [f"[매일 신호] {now:%Y-%m-%d %H:%M} KST"]
    exit_code = 0

    try:
        if "--no-fetch" not in sys.argv:
            refresh_data(lines)
        targets = compute_targets(lines)

        try:
            config = KISConfig.from_env()
        except KISError as error:
            lines.append(f"KIS 미연동 (신호만 출력): {error}")
            config = None

        if config is not None:
            if config.mode == "live" and not live_flag:
                lines.append("[차단] KIS_MODE=live인데 --live 플래그가 없어 주문하지 않습니다")
                execute = False
            lines.append(f"KIS 모드: {'모의투자' if config.mode == 'paper' else '실거래'}")
            client = KISClient(config)
            orders, _, _ = plan_orders(client, targets, lines)
            if execute and orders:
                execute_orders(client, orders, lines)
            elif orders:
                lines.append("(--execute 플래그가 없어 주문을 내지 않았습니다)")
    except Exception as error:  # noqa: BLE001 - the failure itself must be notified
        lines.append(f"[오류] 작업 실패: {error}")
        exit_code = 1

    report = "\n".join(lines)
    print(report)
    if send_telegram(report):
        print("(텔레그램 전송 완료)")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

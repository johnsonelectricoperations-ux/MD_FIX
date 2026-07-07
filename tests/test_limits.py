from decimal import Decimal

from stock.limits import (
    cap_buy_orders,
    daily_loss_limit_from_env,
    kill_switch_triggered,
    max_order_value_from_env,
    record_account_state,
)
from stock.rebalance import Order

PRICES = {"069500": 50_000, "153130": 100_000}


def test_oversized_buy_is_dropped_with_note():
    orders = [Order("069500", "buy", 200)]  # 10,000,000 KRW
    kept, notes = cap_buy_orders(orders, PRICES, Decimal("6000000"))
    assert kept == []
    assert len(notes) == 1 and "한도차단" in notes[0]


def test_sells_are_never_capped():
    orders = [Order("069500", "sell", 1000)]  # 50M KRW sell, far over cap
    kept, notes = cap_buy_orders(orders, PRICES, Decimal("6000000"))
    assert kept == orders and notes == []


def test_buy_within_cap_passes():
    orders = [Order("069500", "buy", 100)]  # 5,000,000 KRW
    kept, notes = cap_buy_orders(orders, PRICES, Decimal("6000000"))
    assert kept == orders and notes == []


def test_kill_switch_trips_on_large_drop(tmp_path):
    state = tmp_path / "state.json"
    record_account_state(Decimal("10000000"), state_file=state)
    message = kill_switch_triggered(Decimal("8000000"), Decimal("0.15"), state_file=state)
    assert message is not None and "킬스위치" in message


def test_kill_switch_quiet_on_normal_day(tmp_path):
    state = tmp_path / "state.json"
    record_account_state(Decimal("10000000"), state_file=state)
    assert kill_switch_triggered(Decimal("9500000"), Decimal("0.15"), state_file=state) is None


def test_kill_switch_quiet_without_history(tmp_path):
    missing = tmp_path / "none.json"
    assert kill_switch_triggered(Decimal("1"), Decimal("0.15"), state_file=missing) is None


def test_limits_read_from_env(monkeypatch):
    monkeypatch.setenv("MAX_ORDER_VALUE_KRW", "3000000")
    monkeypatch.setenv("DAILY_LOSS_LIMIT_PCT", "10")
    assert max_order_value_from_env() == Decimal("3000000")
    assert daily_loss_limit_from_env() == Decimal("0.10")


def test_limit_defaults_without_env(monkeypatch):
    monkeypatch.delenv("MAX_ORDER_VALUE_KRW", raising=False)
    monkeypatch.delenv("DAILY_LOSS_LIMIT_PCT", raising=False)
    assert max_order_value_from_env() == Decimal("6000000")
    assert daily_loss_limit_from_env() == Decimal("0.15")

from decimal import Decimal

from stock.rebalance import Order, compute_orders

PRICES = {"069500": 50_000, "360750": 20_000, "153130": 100_000}


def test_switch_sells_old_asset_and_buys_new_one():
    orders = compute_orders(
        targets={"360750": 0.9},
        holdings={"069500": 100},  # 5,000,000 KRW worth
        prices=PRICES,
        cash=Decimal(0),
    )
    assert orders[0] == Order("069500", "sell", 100)  # sells come first
    buys = [o for o in orders if o.side == "buy"]
    assert len(buys) == 1 and buys[0].code == "360750"
    # 90% of (5,000,000 * 0.99 buffer) / 20,000 = 222 shares
    assert buys[0].quantity == 222


def test_small_drift_within_band_produces_no_orders():
    # Currently ~50% invested, target 55%: 5%p drift, same asset set.
    orders = compute_orders(
        targets={"069500": 0.55},
        holdings={"069500": 100},
        prices=PRICES,
        cash=Decimal(5_000_000),
        band=0.10,
    )
    assert orders == []


def test_full_exit_to_cash_sells_everything():
    orders = compute_orders(
        targets={},
        holdings={"069500": 30, "360750": 10},
        prices=PRICES,
        cash=Decimal(0),
    )
    assert sorted(orders, key=lambda o: o.code) == [
        Order("069500", "sell", 30),
        Order("360750", "sell", 10),
    ]


def test_buys_never_exceed_available_cash():
    # Target 100% of one asset but almost no cash: quantity capped by budget.
    orders = compute_orders(
        targets={"069500": 1.0},
        holdings={},
        prices=PRICES,
        cash=Decimal(120_000),
    )
    assert orders == [Order("069500", "buy", 2)]  # floor(120000/50000)


def test_no_orders_on_empty_account():
    assert (
        compute_orders(targets={"069500": 1.0}, holdings={}, prices=PRICES, cash=Decimal(0)) == []
    )

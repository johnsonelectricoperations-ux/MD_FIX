from decimal import Decimal

import pytest

from stock.kis import KISClient, KISConfig, KISError

CONFIG = KISConfig(app_key="key", app_secret="secret", account_no="12345678-01", mode="paper")

TOKEN_RESPONSE = {"access_token": "tok-1", "expires_in": 86400}
BALANCE_RESPONSE = {
    "rt_cd": "0",
    "output1": [
        {"pdno": "069500", "hldg_qty": "100"},
        {"pdno": "360750", "hldg_qty": "0"},  # closed position must be dropped
    ],
    "output2": [{"dnca_tot_amt": "1500000", "tot_evlu_amt": "6500000"}],
}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Records requests and replays queued responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def make_client(tmp_path, responses):
    session = FakeSession(responses)
    client = KISClient(CONFIG, token_cache=tmp_path / "token.json", session=session)
    return client, session


def test_token_is_cached_across_calls(tmp_path):
    client, session = make_client(
        tmp_path,
        [
            FakeResponse(TOKEN_RESPONSE),
            FakeResponse({"rt_cd": "0", "output": {"stck_prpr": "50000"}}),
            FakeResponse({"rt_cd": "0", "output": {"stck_prpr": "50100"}}),
        ],
    )
    assert client.get_price("069500") == 50000
    assert client.get_price("069500") == 50100
    token_posts = [c for c in session.calls if c[0] == "POST"]
    assert len(token_posts) == 1  # second call reused the cached token


def test_balance_parses_holdings_and_decimal_cash(tmp_path):
    client, _ = make_client(
        tmp_path, [FakeResponse(TOKEN_RESPONSE), FakeResponse(BALANCE_RESPONSE)]
    )
    balance = client.get_balance()
    assert balance.holdings == {"069500": 100}
    assert balance.cash == Decimal("1500000")
    assert balance.total_value == Decimal("6500000")


def test_paper_mode_uses_paper_tr_ids_for_orders(tmp_path):
    client, session = make_client(
        tmp_path,
        [FakeResponse(TOKEN_RESPONSE), FakeResponse({"rt_cd": "0", "output": {"ODNO": "42"}})],
    )
    assert client.place_market_order("069500", 3, "buy") == "42"
    method, url, kwargs = session.calls[-1]
    assert method == "POST" and url.endswith("/order-cash")
    assert kwargs["headers"]["tr_id"] == "VTTC0802U"  # paper buy, not live TTTC0802U
    assert kwargs["json"]["ORD_QTY"] == "3"
    assert "openapivts" in url  # paper host


def test_api_error_body_raises_kis_error(tmp_path):
    client, _ = make_client(
        tmp_path,
        [
            FakeResponse(TOKEN_RESPONSE),
            FakeResponse({"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "주문 불가"}),
        ],
    )
    with pytest.raises(KISError, match="주문 불가"):
        client.place_market_order("069500", 1, "sell")


def test_invalid_order_arguments_rejected_before_any_request(tmp_path):
    client, session = make_client(tmp_path, [])
    with pytest.raises(ValueError):
        client.place_market_order("069500", 0, "buy")
    with pytest.raises(ValueError):
        client.place_market_order("069500", 1, "hold")
    assert session.calls == []


def test_config_from_env_requires_all_keys(monkeypatch):
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO", "KIS_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KIS_APP_KEY", "k")
    with pytest.raises(KISError, match="KIS_APP_SECRET"):
        KISConfig.from_env()


def test_config_from_env_defaults_to_paper(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678-01")
    monkeypatch.delenv("KIS_MODE", raising=False)
    assert KISConfig.from_env().mode == "paper"

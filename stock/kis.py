"""Korea Investment & Securities (KIS) Developers REST API client.

Paper and live trading use different hosts and tr_id codes. The mode comes
from the KIS_MODE environment variable and DEFAULTS TO PAPER (AGENTS.md §5);
call sites add their own --live guard on top.

Endpoint paths and tr_id codes follow the KIS Developers documentation
(https://apiportal.koreainvestment.com). Verify on first connection: run
scripts/daily_signal.py without --execute and check the balance output.

Access tokens are valid ~24h and issuance is rate-limited, so the token is
cached under data/ (gitignored) and reused until it expires.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import requests

BASE_URLS = {
    "paper": "https://openapivts.koreainvestment.com:29443",
    "live": "https://openapi.koreainvestment.com:9443",
}
TR_IDS = {
    "paper": {"balance": "VTTC8434R", "buy": "VTTC0802U", "sell": "VTTC0801U"},
    "live": {"balance": "TTTC8434R", "buy": "TTTC0802U", "sell": "TTTC0801U"},
}
PRICE_TR_ID = "FHKST01010100"  # quotations are mode-independent
MARKET_ORDER = "01"  # ORD_DVSN code for a market order
DEFAULT_TOKEN_CACHE = Path("data/kis_token.json")
TIMEOUT = 30


class KISError(RuntimeError):
    """Raised when the KIS API rejects a request or returns an error body."""


@dataclass(frozen=True)
class KISConfig:
    app_key: str
    app_secret: str
    account_no: str  # "12345678-01" (계좌번호-상품코드)
    mode: str = "paper"

    @classmethod
    def from_env(cls) -> KISConfig:
        names = ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO")
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise KISError(f".env에 다음 항목이 없습니다: {', '.join(missing)}")
        mode = os.environ.get("KIS_MODE", "paper").lower()
        if mode not in BASE_URLS:
            raise KISError(f"KIS_MODE는 paper 또는 live여야 합니다: {mode}")
        account_no = os.environ["KIS_ACCOUNT_NO"]
        if "-" not in account_no:
            raise KISError("KIS_ACCOUNT_NO는 '12345678-01' 형식이어야 합니다")
        return cls(
            app_key=os.environ["KIS_APP_KEY"],
            app_secret=os.environ["KIS_APP_SECRET"],
            account_no=account_no,
            mode=mode,
        )

    @property
    def base_url(self) -> str:
        return BASE_URLS[self.mode]

    @property
    def cano(self) -> str:
        return self.account_no.split("-")[0]

    @property
    def acnt_prdt_cd(self) -> str:
        return self.account_no.split("-")[1]


@dataclass
class Balance:
    cash: Decimal  # deposit (예수금), KRW
    total_value: Decimal  # total account valuation (총평가금액), KRW
    holdings: dict[str, int]  # 6-digit code -> quantity held


class KISClient:
    def __init__(
        self,
        config: KISConfig,
        token_cache: Path = DEFAULT_TOKEN_CACHE,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.token_cache = token_cache
        self.session = session or requests.Session()

    # --- auth -----------------------------------------------------------

    def _token(self) -> str:
        if self.token_cache.exists():
            cached = json.loads(self.token_cache.read_text(encoding="utf-8"))
            fresh = cached.get("expires_at", 0) - time.time() > 60
            if fresh and cached.get("mode") == self.config.mode:
                return cached["access_token"]
        response = self.session.post(
            f"{self.config.base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.config.app_key,
                "appsecret": self.config.app_secret,
            },
            timeout=TIMEOUT,
        )
        payload = response.json()
        if "access_token" not in payload:
            raise KISError(f"토큰 발급 실패: {payload}")
        record = {
            "access_token": payload["access_token"],
            "expires_at": time.time() + int(payload.get("expires_in", 86400)),
            "mode": self.config.mode,
        }
        self.token_cache.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache.write_text(json.dumps(record), encoding="utf-8")
        return record["access_token"]

    def _headers(self, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._token()}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    @staticmethod
    def _check(response: requests.Response) -> dict:
        if response.status_code != 200:
            raise KISError(f"HTTP {response.status_code}: {response.text[:300]}")
        payload = response.json()
        if payload.get("rt_cd") not in (None, "0"):
            raise KISError(f"KIS 오류 [{payload.get('msg_cd')}]: {payload.get('msg1')}")
        return payload

    # --- market data ----------------------------------------------------

    def get_price(self, code: str) -> int:
        """Current price of a KRX-listed symbol in KRW (integer)."""
        response = self.session.get(
            f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers(PRICE_TR_ID),
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
            timeout=TIMEOUT,
        )
        payload = self._check(response)
        return int(payload["output"]["stck_prpr"])

    # --- account --------------------------------------------------------

    def get_balance(self) -> Balance:
        response = self.session.get(
            f"{self.config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers(TR_IDS[self.config.mode]["balance"]),
            params={
                "CANO": self.config.cano,
                "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
            timeout=TIMEOUT,
        )
        payload = self._check(response)
        holdings = {
            row["pdno"]: int(row["hldg_qty"])
            for row in payload.get("output1", [])
            if int(row["hldg_qty"]) > 0
        }
        summary = payload["output2"][0]
        return Balance(
            cash=Decimal(summary["dnca_tot_amt"]),
            total_value=Decimal(summary["tot_evlu_amt"]),
            holdings=holdings,
        )

    # --- orders ---------------------------------------------------------

    def place_market_order(self, code: str, quantity: int, side: str) -> str:
        """Submit a market order; returns the order number. side: 'buy'/'sell'."""
        if side not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell': {side}")
        if quantity <= 0:
            raise ValueError(f"quantity must be positive: {quantity}")
        response = self.session.post(
            f"{self.config.base_url}/uapi/domestic-stock/v1/trading/order-cash",
            headers=self._headers(TR_IDS[self.config.mode][side]),
            json={
                "CANO": self.config.cano,
                "ACNT_PRDT_CD": self.config.acnt_prdt_cd,
                "PDNO": code,
                "ORD_DVSN": MARKET_ORDER,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": "0",
            },
            timeout=TIMEOUT,
        )
        payload = self._check(response)
        return payload.get("output", {}).get("ODNO", "")

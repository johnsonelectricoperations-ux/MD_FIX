"""Telegram notifications. Fail-soft: a delivery failure never aborts the job."""

from __future__ import annotations

import os

import requests

TIMEOUT = 30


def send_telegram(text: str) -> bool:
    """Send `text` to the configured chat. Returns False if unconfigured/failed."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=TIMEOUT,
        )
        return response.ok
    except requests.RequestException:
        return False

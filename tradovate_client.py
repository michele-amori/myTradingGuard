"""
TradovateClient — makes authenticated REST calls to Tradovate
using the accountId and access token captured passively from
the TradingView Desktop proxy traffic.

Used by MyTradingGuard to fetch the real daily trade history
(losses and trade count) at startup and after each new trade.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Callable, Optional
import urllib.request
import urllib.parse
import json


class TradovateClient:

    _BASE = {
        "live": "https://live.tradovateapi.com/v1",
        "demo": "https://demo.tradovateapi.com/v1",
    }

    def __init__(self, env: str = "demo"):
        self._env = env
        self._base_url = self._BASE.get(env, self._BASE["demo"])

        # Set by the proxy as soon as the first authenticated request passes
        self._account_id: Optional[int] = None
        self._token: Optional[str] = None
        self._lock = threading.Lock()

        # Called once when both credentials become available
        self._on_ready: Optional[Callable] = None

    # ------------------------------------------------------------------ #
    #  Credential capture (called by proxy_addon)                         #
    # ------------------------------------------------------------------ #

    def capture(self, account_id: int, token: str) -> bool:
        """
        Store accountId and token extracted from a proxied request.
        Returns True the first time both values become available
        (triggers the on_ready callback if set).
        """
        with self._lock:
            already_had = self._account_id is not None and self._token is not None
            self._account_id = account_id
            self._token = token

            if not already_had and self._on_ready:
                t = threading.Thread(target=self._on_ready, daemon=True)
                t.start()
                return True
        return False

    def on_ready(self, callback: Callable):
        """Register a callback fired once when credentials are first available."""
        self._on_ready = callback

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._account_id is not None and self._token is not None

    # ------------------------------------------------------------------ #
    #  API calls                                                           #
    # ------------------------------------------------------------------ #

    def fetch_daily_losses_and_trades(self) -> tuple[int, int]:
        """
        Returns (losses_today, trades_today) based on real Tradovate data.

        Calls /position/ldeps?masterids={accountId}, then filters:
          - tradeDate == today
          - netPos == 0  (position is closed)
          - soldValue - boughtValue < 0  → loss
        """
        with self._lock:
            account_id = self._account_id
            token = self._token

        if account_id is None or token is None:
            raise RuntimeError("Credentials not available yet")

        positions = self._get(f"/position/ldeps", {"masterids": str(account_id)})

        today = date.today()
        losses = 0
        trades = 0

        for pos in positions:
            # Filter by today's trade date
            td = pos.get("tradeDate", {})
            if not isinstance(td, dict):
                continue
            pos_date = date(td.get("year", 0), td.get("month", 0), td.get("day", 0))
            if pos_date != today:
                continue

            net_pos = int(pos.get("netPos", 0))
            if net_pos != 0:
                continue  # still open — skip

            sold_value = float(pos.get("soldValue", 0))
            bought_value = float(pos.get("boughtValue", 0))
            pnl = sold_value - bought_value

            trades += 1
            if pnl < 0:
                losses += 1

        return losses, trades

    # ------------------------------------------------------------------ #
    #  HTTP helper                                                         #
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: dict | None = None) -> list:
        """Makes an authenticated GET request. Returns parsed JSON list."""
        url = self._base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")

        data = json.loads(body)
        return data if isinstance(data, list) else []

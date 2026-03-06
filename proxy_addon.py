"""
MyTradingGuardAddon — mitmproxy addon that intercepts order requests
to the broker and blocks them if the rules are not satisfied.

How it works:
  REQUEST  → checks rules → if blocked, returns 403 before
             the request reaches Tradovate
  RESPONSE → if 200/201 and order succeeded → updates the state
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from mitmproxy import http

from config import Config
from notifier import Notifier
from rules_engine import RulesEngine
from trade_state import TradeState


# ------------------------------------------------------------------ #
#  URL patterns for each broker                                       #
# ------------------------------------------------------------------ #

BROKER_PATTERNS: dict[str, dict] = {
    "tradovate": {
        "hosts": [
            "live.tradovateapi.com",
            "demo.tradovateapi.com",
            "tv-live.tradovateapi.com",
            "tv-demo.tradovateapi.com",
            "md.tradovateapi.com",
        ],
        # TradingView Desktop: POST /accounts/{id}/orders with form-encoded body
        # e.g.: instrument=MNQH6&qty=1&side=buy&type=market&...
        "order_paths": [
            r"/accounts/\w+/orders",   # TradingView Desktop (tv-demo/tv-live)
            r"/v1/order/placeorder",   # API nativa Tradovate
            r"/v1/order/placeoco",
            r"/v1/order/placeoso",
            r"/v1/order/placebracket",
        ],
        # Form-encoded body params that identify an order request
        "order_body_params": ["instrument", "side", "qty"],
        # Field that indicates success in the JSON response
        "success_field": "orderId",
    },
    "interactive_brokers": {
        "hosts": [
            "api.ibkr.com",
            "localhost:5000",   # IB Gateway locale
            "localhost:4001",
        ],
        "order_paths": [
            r"/v1/api/iserver/account/\w+/orders",
            r"/v1/api/iserver/account/orders",
        ],
        "success_field": "order_id",
    },
}


class MyTradingGuardAddon:

    def __init__(self, state: TradeState, cfg: Config):
        self.state = state
        self.cfg = cfg
        self.engine = RulesEngine()
        self._patterns = BROKER_PATTERNS.get(cfg.broker, {})
        self.notifier = Notifier(
            sound_enabled=cfg.sound_enabled,
            notify_allowed=cfg.notify_allowed,
        )
        print(f"[MyTradingGuard] Addon active — broker: {cfg.broker} ({cfg.broker_env})")

    # ------------------------------------------------------------------ #
    #  Hook: REQUEST                                                      #
    # ------------------------------------------------------------------ #

    def request(self, flow: http.HTTPFlow) -> None:
        if not self._is_order_request(flow):
            return

        # Reload config if the file has been modified (hot-reload)
        try:
            self.cfg.reload()
        except Exception:
            pass

        ok, reason = self.engine.check_all(self.state, self.cfg)

        if not ok:
            self._block(flow, reason)
        else:
            self._log("ALLOWED", flow.request.path)
            self.notifier.allowed(flow.request.path)

    # ------------------------------------------------------------------ #
    #  Hook: RESPONSE                                                     #
    # ------------------------------------------------------------------ #

    def response(self, flow: http.HTTPFlow) -> None:
        if not self._is_order_request(flow):
            return

        # Don't track responses for orders we already blocked
        if flow.response.status_code == 403:
            return

        if flow.response.status_code in (200, 201):
            try:
                body = json.loads(flow.response.content)
                if self._is_successful_order(body):
                    symbol, direction = self._extract_order_info(flow)
                    self.state.record_trade(symbol=symbol, direction=direction)
                    self._log("TRACKED", f"Trade recorded #{self.state.daily_count}")
            except Exception as e:
                self._log("WARN", f"Response parsing failed: {e}")

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _is_order_request(self, flow: http.HTTPFlow) -> bool:
        """True if the request is an order to the configured broker."""
        if not self._patterns:
            return False

        host = flow.request.pretty_host
        path = flow.request.path
        method = flow.request.method

        # POST only
        if method != "POST":
            return False

        # Broker host check
        if not any(h in host for h in self._patterns.get("hosts", [])):
            return False

        # Path must match one of the order endpoints
        if not any(re.search(p, path) for p in self._patterns.get("order_paths", [])):
            return False

        # For /accounts/{id}/orders, verify that the body contains order params
        # (distinguishes an order POST from other POSTs on the same path)
        required = self._patterns.get("order_body_params", [])
        if required and re.search(r"/accounts/\w+/orders", path):
            try:
                body = flow.request.content.decode("utf-8", errors="replace")
                return all(p in body for p in required)
            except Exception:
                return False

        return True

    def _block(self, flow: http.HTTPFlow, reason: str):
        """Blocks the request by returning a 403."""
        self.state.record_block(reason)
        self._log("BLOCKED", reason)
        flow.response = http.Response.make(
            403,
            json.dumps({"error": "MyTradingGuard", "message": reason, "blocked": True}),
            {"Content-Type": "application/json; charset=utf-8"},
        )

    def _is_successful_order(self, body: dict) -> bool:
        success_field = self._patterns.get("success_field", "orderId")
        # Handles both direct response {"orderId": ...}
        # and array [{"orderId": ...}]
        if isinstance(body, list):
            return bool(body) and success_field in body[0]
        return success_field in body

    def _extract_order_info(self, flow: http.HTTPFlow) -> tuple[str, str]:
        """Extracts symbol and direction from the request body (form-encoded or JSON)."""
        try:
            from urllib.parse import parse_qs
            body_str = flow.request.content.decode("utf-8", errors="replace")
            # Try form-encoded first (used by TradingView Desktop)
            params = parse_qs(body_str)
            if params:
                symbol = params.get("instrument", params.get("symbol", [""]))[0]
                side = params.get("side", params.get("action", [""]))[0]
                direction = {"buy": "LONG", "sell": "SHORT"}.get(side.lower(), side.upper())
                return str(symbol), str(direction)
            # Fallback JSON (native Tradovate API)
            body = json.loads(body_str)
            symbol = body.get("symbol", body.get("contractId", ""))
            action = body.get("action", body.get("side", ""))
            direction = {"Buy": "LONG", "Sell": "SHORT"}.get(action, action)
            return str(symbol), str(direction)
        except Exception:
            return "", ""

    @staticmethod
    def _log(level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"BLOCKED": "🔴", "ALLOWED": "🟢", "TRACKED": "📝", "WARN": "⚠️"}
        icon = icons.get(level, "•")
        print(f"[{ts}] {icon} {level}: {msg}")


# ------------------------------------------------------------------ #
#  Entry point for `mitmdump -s proxy_addon.py`                      #
# ------------------------------------------------------------------ #

def load_addon():
    cfg = Config.load()
    state = TradeState()
    return MyTradingGuardAddon(state=state, cfg=cfg)


# Required when mitmproxy loads this file directly
_cfg = Config.load()
_state = TradeState()
addons = [MyTradingGuardAddon(state=_state, cfg=_cfg)]

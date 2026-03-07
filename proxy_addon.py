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
from tradovate_client import TradovateClient


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
        # Position snapshot for passive loss detection (fallback)
        self._last_positions: dict = {}

        # Tradovate REST client — populated as soon as credentials are captured
        self._tv_client = TradovateClient(env=cfg.broker_env)
        self._tv_client.on_ready(self._on_credentials_ready)

        print(f"[MyTradingGuard] Addon active — broker: {cfg.broker} ({cfg.broker_env})")

    # ------------------------------------------------------------------ #
    #  Hook: REQUEST                                                      #
    # ------------------------------------------------------------------ #

    def request(self, flow: http.HTTPFlow) -> None:
        # Always try to capture credentials from any broker request
        if self._is_broker_request(flow):
            self._capture_credentials(flow)

        if not self._is_order_request(flow):
            return

        # Reload config if the file has been modified (hot-reload)
        try:
            self.cfg.reload()
        except Exception:
            pass

        # Check all standard rules (time window, cooldown, max trades, max losses)
        ok, reason = self.engine.check_all(self.state, self.cfg)
        if not ok:
            self._block(flow, reason)
            return

        # Check order size (per-order rule, needs qty from request body)
        qty = self._extract_qty(flow)
        ok_size, reason_size = self.engine.check_order_size(qty, self.cfg)
        if not ok_size:
            self._block(flow, reason_size)
            return

        self._log("ALLOWED", flow.request.path)
        self.notifier.allowed(flow.request.path)

    # ------------------------------------------------------------------ #
    #  Hook: RESPONSE                                                     #
    # ------------------------------------------------------------------ #

    def response(self, flow: http.HTTPFlow) -> None:
        # Track position changes to detect losing trades
        if self._is_positions_response(flow):
            self._track_positions(flow)
            return

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

    def _on_credentials_ready(self):
        """
        Called once in a background thread when accountId + token
        are first captured. Fetches the real daily history from Tradovate
        and syncs trade_state with accurate loss/trade counts.
        """
        try:
            self._log("INFO", "Credentials captured — fetching daily history from Tradovate...")
            losses, trades = self._tv_client.fetch_daily_losses_and_trades()
            self.state.sync_from_api(losses=losses, trades=trades)
            self._log("INFO", f"Daily history loaded: {trades} trade(s), {losses} loss(es) today")
        except Exception as e:
            self._log("WARN", f"Could not fetch daily history: {e}")

    def _is_broker_request(self, flow: http.HTTPFlow) -> bool:
        """True if the request is going to any broker host (not just orders)."""
        if not self._patterns:
            return False
        host = flow.request.pretty_host
        return any(h in host for h in self._patterns.get("hosts", []))

    def _capture_credentials(self, flow: http.HTTPFlow):
        """
        Extracts accountId from the URL path and the Bearer token
        from the Authorization header, then passes them to the client.
        """
        # accountId from path: /accounts/{accountId}/...
        path = flow.request.path
        m = re.search(r"/accounts/(\d+)/", path)
        if not m:
            return
        try:
            account_id = int(m.group(1))
        except ValueError:
            return

        # Bearer token from Authorization header
        auth = flow.request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return
        token = auth.removeprefix("Bearer ").strip()
        if not token:
            return

        self._tv_client.capture(account_id, token)

    def _is_positions_response(self, flow: http.HTTPFlow) -> bool:
        """True if this is a GET positions response from the broker."""
        if flow.request.method != "GET":
            return False
        host = flow.request.pretty_host
        path = flow.request.path
        if not any(h in host for h in self._patterns.get("hosts", [])):
            return False
        return bool(re.search(r"/accounts/\w+/positions", path))

    def _track_positions(self, flow: http.HTTPFlow) -> None:
        """
        Compares the current positions snapshot with the previous one.
        When a position closes (netPos goes to 0 or disappears) and
        soldValue - boughtValue < 0, records a loss.
        """
        if flow.response.status_code not in (200, 201):
            return
        try:
            data = json.loads(flow.response.content)
            positions = data if isinstance(data, list) else data.get("positions", [])
            if not isinstance(positions, list):
                return

            # Build current snapshot keyed by position id (fallback to contractId)
            current: dict = {}
            for p in positions:
                key = p.get("id") or p.get("contractId")
                if key is not None:
                    current[key] = p

            # Compare with previous snapshot
            for key, prev in self._last_positions.items():
                prev_net = int(prev.get("netPos", 0))
                if prev_net == 0:
                    continue  # was already flat, skip

                curr = current.get(key)
                curr_net = int(curr.get("netPos", 0)) if curr else 0

                if curr_net == 0:
                    # Position just closed — check P&L
                    sold_val   = float(prev.get("soldValue", 0))
                    bought_val = float(prev.get("boughtValue", 0))
                    pnl = sold_val - bought_val
                    symbol = str(prev.get("contractId", ""))

                    if pnl < 0:
                        self.state.record_loss(pnl=pnl, symbol=symbol)
                        self._log("LOSS", f"Losing trade — P&L: {pnl:.2f} ({symbol})")
                    else:
                        self._log("WIN", f"Winning trade — P&L: {pnl:.2f} ({symbol})")

            self._last_positions = current

        except Exception as e:
            self._log("WARN", f"Position tracking failed: {e}")

    def _extract_qty(self, flow: http.HTTPFlow) -> int:
        """Extracts the order quantity from the request body."""
        try:
            from urllib.parse import parse_qs
            body_str = flow.request.content.decode("utf-8", errors="replace")
            params = parse_qs(body_str)
            if params:
                return int(params.get("qty", ["0"])[0])
            body = json.loads(body_str)
            return int(body.get("qty", body.get("quantity", 0)))
        except Exception:
            return 0

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

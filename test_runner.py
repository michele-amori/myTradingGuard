"""
test_runner.py — offline test suite for MyTradingGuard.

Tests the full pipeline without TradingView, without Tradovate,
and without markets being open. Covers:

  1. Rules engine — each rule individually
  2. Proxy interception — fake HTTP requests through mitmproxy
  3. Tradovate client — mock API server returning fake position data
  4. Integration — full block/allow flow end to end

Run with:
    python3 test_runner.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── colours ────────────────────────────────────────────────────────── #
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_passed = 0
_failed = 0


def ok(label: str):
    global _passed
    _passed += 1
    print(f"  {GREEN}✓{RESET}  {label}")


def fail(label: str, detail: str = ""):
    global _failed
    _failed += 1
    msg = f"  {RED}✗{RESET}  {label}"
    if detail:
        msg += f"\n      {RED}{detail}{RESET}"
    print(msg)


def section(title: str):
    print(f"\n{BOLD}{YELLOW}── {title} {'─' * (50 - len(title))}{RESET}")


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


# ================================================================== #
#  1. Rules engine                                                    #
# ================================================================== #

# Isolated state file for tests (avoids polluting ~/.mytradingguard/state.json)
_TMP_STATE = Path(tempfile.mktemp(suffix=".json"))


def _fresh_state() -> "TradeState":
    """Returns a TradeState that reads/writes to a temp file, not the real one."""
    import trade_state as ts_module
    with patch.object(ts_module, "STATE_FILE", _TMP_STATE):
        from trade_state import TradeState
        s = TradeState.__new__(TradeState)
        import threading
        s._lock = threading.Lock()
        s._state = {
            "date": str(date.today()),
            "daily_count": 0,
            "daily_losses": 0,
            "last_trade_time": None,
        }
        s._events = []
        return s


def test_rules_engine():
    section("Rules Engine")

    from config import Config
    from rules_engine import RulesEngine
    from trade_state import TradeState

    cfg = Config.load()
    engine = RulesEngine()
    state = _fresh_state()

    # ── Time window ───────────────────────────────────────────────── #
    import pytz
    from unittest.mock import patch

    tz = pytz.timezone(cfg.time_window.timezone)

    # Force time inside first window
    window = cfg.time_window.windows[0]
    h, m = map(int, window["start"].split(":"))
    inside_dt = datetime.now(tz).replace(hour=h, minute=m + 1, second=0)
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = inside_dt
        ok_val, _ = engine.check_time_window(state, cfg)
        check("Time window: inside window → allowed", ok_val)

    # Force time outside all windows (midnight)
    outside_dt = datetime.now(tz).replace(hour=0, minute=0, second=0)
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = outside_dt
        ok_val, _ = engine.check_time_window(state, cfg)
        check("Time window: outside window → blocked", not ok_val)

    # Disable rule
    orig = cfg.time_window.active
    cfg.time_window.active = False
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = outside_dt
        ok_val, _ = engine.check_time_window(state, cfg)
        check("Time window: active=False → always allowed", ok_val)
    cfg.time_window.active = orig

    # ── Cooldown ──────────────────────────────────────────────────── #
    state2 = TradeState()
    # Fake a trade 1 minute ago
    state2._state["last_trade_time"] = (datetime.now() - timedelta(minutes=1)).isoformat()
    ok_val, msg = engine.check_cooldown(state2, cfg)
    check("Cooldown: 1min elapsed, 30min required → blocked", not ok_val)

    # Fake a trade 31 minutes ago
    state2._state["last_trade_time"] = (datetime.now() - timedelta(minutes=31)).isoformat()
    ok_val, _ = engine.check_cooldown(state2, cfg)
    check("Cooldown: 31min elapsed, 30min required → allowed", ok_val)

    orig = cfg.cooldown.active
    cfg.cooldown.active = False
    ok_val, _ = engine.check_cooldown(state2, cfg)
    check("Cooldown: active=False → always allowed", ok_val)
    cfg.cooldown.active = orig

    # ── Max daily trades ──────────────────────────────────────────── #
    state3 = TradeState()
    state3._state["daily_count"] = cfg.max_daily_trades.value - 1
    ok_val, _ = engine.check_max_trades(state3, cfg)
    check(f"Max trades: {cfg.max_daily_trades.value - 1}/{cfg.max_daily_trades.value} → allowed", ok_val)

    state3._state["daily_count"] = cfg.max_daily_trades.value
    ok_val, _ = engine.check_max_trades(state3, cfg)
    check(f"Max trades: {cfg.max_daily_trades.value}/{cfg.max_daily_trades.value} → blocked", not ok_val)

    orig = cfg.max_daily_trades.active
    cfg.max_daily_trades.active = False
    ok_val, _ = engine.check_max_trades(state3, cfg)
    check("Max trades: active=False → always allowed", ok_val)
    cfg.max_daily_trades.active = orig

    # ── Max daily losses ──────────────────────────────────────────── #
    state4 = TradeState()
    state4._state["daily_losses"] = cfg.max_daily_losses.value - 1
    ok_val, _ = engine.check_max_losses(state4, cfg)
    check(f"Max losses: {cfg.max_daily_losses.value - 1}/{cfg.max_daily_losses.value} → allowed", ok_val)

    state4._state["daily_losses"] = cfg.max_daily_losses.value
    ok_val, _ = engine.check_max_losses(state4, cfg)
    check(f"Max losses: {cfg.max_daily_losses.value}/{cfg.max_daily_losses.value} → blocked", not ok_val)

    orig = cfg.max_daily_losses.active
    cfg.max_daily_losses.active = False
    ok_val, _ = engine.check_max_losses(state4, cfg)
    check("Max losses: active=False → always allowed", ok_val)
    cfg.max_daily_losses.active = orig

    # ── Max order size ────────────────────────────────────────────── #
    ok_val, _ = engine.check_order_size(cfg.max_order_size.value, cfg)
    check(f"Order size: {cfg.max_order_size.value} == limit → allowed", ok_val)

    ok_val, _ = engine.check_order_size(cfg.max_order_size.value + 1, cfg)
    check(f"Order size: {cfg.max_order_size.value + 1} > limit → blocked", not ok_val)

    orig = cfg.max_order_size.active
    cfg.max_order_size.active = False
    ok_val, _ = engine.check_order_size(999, cfg)
    check("Order size: active=False → always allowed", ok_val)
    cfg.max_order_size.active = orig

    # ── Priority: max_trades has priority over max_losses ─────────── #
    state5 = _fresh_state()
    state5._state["daily_count"]  = cfg.max_daily_trades.value
    state5._state["daily_losses"] = cfg.max_daily_losses.value
    # Patch time so check_time_window passes (inside first window)
    window = cfg.time_window.windows[0]
    h, m = map(int, window["start"].split(":"))
    inside_dt = datetime.now(tz).replace(hour=h, minute=m + 1, second=0)
    # Patch only datetime.now inside rules_engine, preserve timedelta
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.side_effect = lambda tz=None: inside_dt
        mock_dt.side_effect = None
        ok_val, reason = engine.check_all(state5, cfg)
    check(
        "Priority: max_trades blocks before max_losses",
        not ok_val and "Daily limit" in reason,
        f"got: {reason!r}",
    )


# ================================================================== #
#  2. TradeState — sync_from_api                                     #
# ================================================================== #

def test_trade_state():
    section("TradeState")

    state = _fresh_state()
    state._state["daily_count"]  = 1
    state._state["daily_losses"] = 1

    # API returns higher values → should update
    state.sync_from_api(losses=3, trades=4)
    check("sync_from_api: updates with higher API values",
          state.daily_losses == 3 and state.daily_count == 4)

    # API returns lower values → should NOT overwrite
    state.sync_from_api(losses=1, trades=1)
    check("sync_from_api: does not overwrite with lower values",
          state.daily_losses == 3 and state.daily_count == 4)

    # record_loss increments correctly
    state2 = _fresh_state()
    state2._state["daily_losses"] = 0
    state2.record_loss(pnl=-100.0, symbol="MNQH6")
    check("record_loss: increments daily_losses", state2.daily_losses == 1)


# ================================================================== #
#  3. TradovateClient — mock API server                              #
# ================================================================== #

class _MockTradovateHandler(BaseHTTPRequestHandler):
    """Minimal mock of Tradovate REST API for testing."""

    TODAY = date.today()

    POSITIONS = [
        # Losing trade today (closed)
        {
            "id": 1, "accountId": 99999, "contractId": 123,
            "netPos": 0, "boughtValue": 1000.0, "soldValue": 900.0,
            "tradeDate": {"year": TODAY.year, "month": TODAY.month, "day": TODAY.day},
        },
        # Winning trade today (closed)
        {
            "id": 2, "accountId": 99999, "contractId": 123,
            "netPos": 0, "boughtValue": 900.0, "soldValue": 1000.0,
            "tradeDate": {"year": TODAY.year, "month": TODAY.month, "day": TODAY.day},
        },
        # Losing trade yesterday (should be ignored)
        {
            "id": 3, "accountId": 99999, "contractId": 123,
            "netPos": 0, "boughtValue": 1000.0, "soldValue": 800.0,
            "tradeDate": {"year": TODAY.year, "month": TODAY.month, "day": TODAY.day - 1},
        },
        # Open position today (netPos != 0, should be ignored)
        {
            "id": 4, "accountId": 99999, "contractId": 123,
            "netPos": 1, "boughtValue": 500.0, "soldValue": 0.0,
            "tradeDate": {"year": TODAY.year, "month": TODAY.month, "day": TODAY.day},
        },
    ]

    def do_GET(self):
        if "/position/ldeps" in self.path:
            body = json.dumps(self.POSITIONS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass   # silence server logs


def test_tradovate_client():
    section("TradovateClient (mock server)")

    from tradovate_client import TradovateClient

    # Start mock server on a random port
    server = HTTPServer(("127.0.0.1", 0), _MockTradovateHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Point client at mock server
    client = TradovateClient(env="demo")
    client._base_url = f"http://127.0.0.1:{port}"
    client._account_id = 99999
    client._token = "fake_token"

    losses, trades = client.fetch_daily_losses_and_trades()

    check("Mock server: 2 closed trades today", trades == 2, f"got {trades}")
    check("Mock server: 1 losing trade today",  losses == 1, f"got {losses}")

    server.shutdown()

    # Test capture + on_ready callback
    client2 = TradovateClient(env="demo")
    ready_called = threading.Event()
    client2.on_ready(lambda: ready_called.set())

    check("Before capture: not ready", not client2.ready)
    client2.capture(account_id=12345, token="abc123")
    ready_called.wait(timeout=2)
    check("After capture: ready", client2.ready)
    check("on_ready callback fired", ready_called.is_set())


# ================================================================== #
#  4. Proxy credential capture                                       #
# ================================================================== #

def test_credential_capture():
    section("Proxy — credential capture")

    from config import Config
    from trade_state import TradeState
    from proxy_addon import MyTradingGuardAddon

    cfg = Config.load()
    state = TradeState()
    addon = MyTradingGuardAddon(state=state, cfg=cfg)

    # Build a fake mitmproxy flow with Authorization header
    flow = MagicMock()
    flow.request.method = "POST"
    flow.request.pretty_host = "tv-demo.tradovateapi.com"
    flow.request.path = "/accounts/987654/orders"
    flow.request.headers = {"Authorization": "Bearer eyFakeToken123"}
    flow.request.content = b"instrument=MNQH6&qty=1&side=buy&type=market"

    check("Client not ready before any request", not addon._tv_client.ready)

    addon._capture_credentials(flow)

    check("accountId extracted correctly",
          addon._tv_client._account_id == 987654,
          f"got {addon._tv_client._account_id}")
    check("token extracted correctly",
          addon._tv_client._token == "eyFakeToken123",
          f"got {addon._tv_client._token!r}")
    check("client ready after capture", addon._tv_client.ready)


# ================================================================== #
#  5. Integration — full block/allow flow                            #
# ================================================================== #

def test_integration():
    section("Integration — block / allow flow")

    import pytz
    from config import Config
    from trade_state import TradeState
    from rules_engine import RulesEngine

    cfg  = Config.load()
    engine = RulesEngine()
    tz = pytz.timezone(cfg.time_window.timezone)

    # ── Scenario A: all rules pass ────────────────────────────────── #
    state = _fresh_state()
    window = cfg.time_window.windows[0]
    h, m = map(int, window["start"].split(":"))
    inside = datetime.now(tz).replace(hour=h, minute=m + 1, second=0)

    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = inside
        ok_val, reason = engine.check_all(state, cfg)
    check("Integration A: all rules pass → allowed", ok_val, reason)

    # ── Scenario B: outside time window ───────────────────────────── #
    state = _fresh_state()
    outside = datetime.now(tz).replace(hour=0, minute=0, second=0)
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = outside
        ok_val, reason = engine.check_all(state, cfg)
    check("Integration B: outside window → blocked", not ok_val and "Outside" in reason, reason)

    # ── Scenario C: max losses reached ────────────────────────────── #
    state = _fresh_state()
    state._state["daily_losses"] = cfg.max_daily_losses.value
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = inside
        ok_val, reason = engine.check_all(state, cfg)
    check("Integration C: max losses reached → blocked", not ok_val and "loss" in reason.lower(), reason)

    # ── Scenario D: max trades blocks before max losses ───────────── #
    state = _fresh_state()
    state._state["daily_count"]  = cfg.max_daily_trades.value
    state._state["daily_losses"] = cfg.max_daily_losses.value
    with patch("rules_engine.datetime") as mock_dt:
        mock_dt.now.return_value = inside
        ok_val, reason = engine.check_all(state, cfg)
    check("Integration D: max_trades priority over max_losses",
          not ok_val and "Daily limit" in reason, reason)

    # ── Scenario E: order size check ─────────────────────────────── #
    state = _fresh_state()
    ok_size, _ = engine.check_order_size(cfg.max_order_size.value + 1, cfg)
    check(f"Integration E: order qty {cfg.max_order_size.value + 1} > limit → blocked", not ok_size)


# ================================================================== #
#  Main                                                               #
# ================================================================== #

if __name__ == "__main__":
    print(f"\n{BOLD}MyTradingGuard — Test Suite{RESET}")
    print("=" * 55)

    try:
        test_rules_engine()
        test_trade_state()
        test_tradovate_client()
        test_credential_capture()
        test_integration()
    except Exception as e:
        import traceback
        fail("Unexpected exception", traceback.format_exc())

    print()
    total = _passed + _failed
    color = GREEN if _failed == 0 else RED
    print(f"{color}{BOLD}Results: {_passed}/{total} passed", end="")
    if _failed:
        print(f"  —  {_failed} FAILED", end="")
    print(RESET + "\n")
    sys.exit(0 if _failed == 0 else 1)

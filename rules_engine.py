"""
RulesEngine — evaluates trading rules against the current state.
Each rule returns (ok: bool, message: str).

Rules are skipped entirely if their "active" flag is False in config.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytz

if TYPE_CHECKING:
    from trade_state import TradeState
    from config import Config


class RulesEngine:

    def check_all(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        """
        Runs all checks in order.
        Returns (True, "") if all pass, (False, reason) on first failure.
        Inactive rules are skipped.
        """
        checks = [
            self.check_time_window,
            self.check_cooldown,
            self.check_max_trades,
            self.check_max_losses,
        ]
        for check in checks:
            ok, msg = check(state, cfg)
            if not ok:
                return False, msg
        return True, ""

    # ------------------------------------------------------------------ #
    #  Rule 1 — Time window                                               #
    # ------------------------------------------------------------------ #

    def check_time_window(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        rule = cfg.time_window
        if not rule.active or not rule.windows:
            return True, ""

        tz = pytz.timezone(rule.timezone)
        now = datetime.now(tz)
        now_time = now.time()

        for window in rule.windows:
            start = _parse_time(window["start"])
            end = _parse_time(window["end"])
            if start <= now_time <= end:
                return True, ""

        windows_str = ", ".join(f"{w['start']}–{w['end']}" for w in rule.windows)
        return (
            False,
            f"Outside trading hours. Allowed windows: {windows_str} ({rule.timezone})",
        )

    # ------------------------------------------------------------------ #
    #  Rule 2 — Cooldown                                                  #
    # ------------------------------------------------------------------ #

    def check_cooldown(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        rule = cfg.cooldown
        if not rule.active or rule.minutes <= 0:
            return True, ""

        last = state.last_trade_time
        if last is None:
            return True, ""

        elapsed = datetime.now() - last
        required = timedelta(minutes=rule.minutes)

        if elapsed >= required:
            return True, ""

        remaining = required - elapsed
        mins = int(remaining.total_seconds() // 60)
        secs = int(remaining.total_seconds() % 60)
        return (
            False,
            f"Cooldown active: wait {mins}m {secs}s more "
            f"(last trade: {last.strftime('%H:%M:%S')})",
        )

    # ------------------------------------------------------------------ #
    #  Rule 3 — Max daily trades                                          #
    # ------------------------------------------------------------------ #

    def check_max_trades(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        rule = cfg.max_daily_trades
        if not rule.active or rule.value <= 0:
            return True, ""

        count = state.daily_count
        if count < rule.value:
            return True, ""

        return (
            False,
            f"Daily limit reached: {count}/{rule.value} trades",
        )

    # ------------------------------------------------------------------ #
    #  Rule 4 — Max daily losing trades                                   #
    # ------------------------------------------------------------------ #

    def check_max_losses(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        rule = cfg.max_daily_losses
        if not rule.active or rule.value <= 0:
            return True, ""

        losses = state.daily_losses
        if losses < rule.value:
            return True, ""

        return (
            False,
            f"Max losing trades reached: {losses}/{rule.value} losses today",
        )

    # ------------------------------------------------------------------ #
    #  Rule 5 — Max order size (per-order, needs qty from request body)   #
    # ------------------------------------------------------------------ #

    def check_order_size(self, qty: int, cfg: "Config") -> tuple[bool, str]:
        rule = cfg.max_order_size
        if not rule.active or rule.value <= 0:
            return True, ""

        if qty <= rule.value:
            return True, ""

        return (
            False,
            f"Order size too large: {qty} contracts (max allowed: {rule.value})",
        )


# ------------------------------------------------------------------ #
#  Helper                                                              #
# ------------------------------------------------------------------ #

def _parse_time(t: str):
    """Converts 'HH:MM' to datetime.time."""
    h, m = map(int, t.split(":"))
    from datetime import time
    return time(h, m)

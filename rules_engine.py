"""
RulesEngine — evaluates trading rules against the current state.
Each rule returns (ok: bool, message: str).
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
        if not cfg.time_windows:
            return True, ""

        tz = pytz.timezone(cfg.timezone)
        now = datetime.now(tz)
        now_time = now.time()

        for window in cfg.time_windows:
            start = _parse_time(window["start"])
            end = _parse_time(window["end"])
            if start <= now_time <= end:
                return True, ""

        windows_str = ", ".join(
            f"{w['start']}–{w['end']}" for w in cfg.time_windows
        )
        return (
            False,
            f"Outside trading hours. Allowed windows: {windows_str} ({cfg.timezone})",
        )

    # ------------------------------------------------------------------ #
    #  Rule 2 — Cooldown                                                  #
    # ------------------------------------------------------------------ #

    def check_cooldown(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        if cfg.cooldown_minutes <= 0:
            return True, ""

        last = state.last_trade_time
        if last is None:
            return True, ""

        elapsed = datetime.now() - last
        required = timedelta(minutes=cfg.cooldown_minutes)

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
        if cfg.max_daily_trades <= 0:
            return True, ""

        count = state.daily_count
        if count < cfg.max_daily_trades:
            return True, ""

        return (
            False,
            f"Daily limit reached: {count}/{cfg.max_daily_trades} trades",
        )

    # ------------------------------------------------------------------ #
    #  Rule 4 — Max daily losing trades                                   #
    # ------------------------------------------------------------------ #

    def check_max_losses(self, state: "TradeState", cfg: "Config") -> tuple[bool, str]:
        if cfg.max_daily_losses <= 0:
            return True, ""

        losses = state.daily_losses
        if losses < cfg.max_daily_losses:
            return True, ""

        return (
            False,
            f"Max losing trades reached: {losses}/{cfg.max_daily_losses} losses today",
        )

    # ------------------------------------------------------------------ #
    #  Rule 5 — Max order size (checked per-order, needs qty from request) #
    # ------------------------------------------------------------------ #

    def check_order_size(self, qty: int, cfg: "Config") -> tuple[bool, str]:
        if cfg.max_order_size <= 0:
            return True, ""

        if qty <= cfg.max_order_size:
            return True, ""

        return (
            False,
            f"Order size too large: {qty} contracts (max allowed: {cfg.max_order_size})",
        )


# ------------------------------------------------------------------ #
#  Helper                                                              #
# ------------------------------------------------------------------ #

def _parse_time(t: str):
    """Converts 'HH:MM' to datetime.time."""
    h, m = map(int, t.split(":"))
    from datetime import time
    return time(h, m)

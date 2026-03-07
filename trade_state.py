"""
TradeState — manages and persists the daily trade state.
Thread-safe. Resets automatically at the start of each new day.
"""

import json
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Optional

STATE_FILE = Path.home() / ".mytradingguard" / "state.json"


class TradeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict = {
            "date": str(date.today()),
            "daily_count": 0,
            "daily_losses": 0,
            "last_trade_time": None,
        }
        self._events: list[dict] = []   # in-memory log of the last N events
        self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    saved = json.load(f)
                # Load only if still the same day
                if saved.get("date") == str(date.today()):
                    self._state = saved
            except Exception:
                pass   # corrupted file → start fresh

    def _save(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    def _ensure_today(self):
        """Resets the counter if it's a new day (must be called inside lock)."""
        today = str(date.today())
        if self._state["date"] != today:
            self._state = {
                "date": today,
                "daily_count": 0,
                "daily_losses": 0,
                "last_trade_time": None,
            }

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def record_trade(self, symbol: str = "", direction: str = ""):
        """Records a completed trade."""
        with self._lock:
            self._ensure_today()
            self._state["daily_count"] += 1
            now = datetime.now()
            self._state["last_trade_time"] = now.isoformat()
            self._save()
            self._add_event("PASSED", f"{direction} {symbol}".strip() or "order", now)

    def record_loss(self, pnl: float = 0.0, symbol: str = ""):
        """Records a losing trade (closed at a loss)."""
        with self._lock:
            self._ensure_today()
            self._state["daily_losses"] = self._state.get("daily_losses", 0) + 1
            self._save()
            detail = f"Loss #{self._state['daily_losses']}"
            if symbol:
                detail += f" — {symbol}"
            if pnl:
                detail += f" (P&L: {pnl:.2f})"
            self._add_event("LOSS", detail, datetime.now())

    def sync_from_api(self, losses: int, trades: int):
        """
        Overwrites daily_losses and daily_count with authoritative data
        fetched directly from the Tradovate API.
        Only applies if the values from the API are >= what we already have
        (avoids overwriting state with stale data if the call is delayed).
        """
        with self._lock:
            self._ensure_today()
            self._state["daily_losses"] = max(
                self._state.get("daily_losses", 0), losses
            )
            self._state["daily_count"] = max(
                self._state.get("daily_count", 0), trades
            )
            self._save()

    def record_block(self, reason: str):
        """Records a blocked order."""
        self._add_event("BLOCKED", reason, datetime.now())

    def _add_event(self, kind: str, detail: str, ts: datetime):
        self._events.append({"kind": kind, "detail": detail, "ts": ts})
        # Keep only the last 50 events
        if len(self._events) > 50:
            self._events = self._events[-50:]

    # ------------------------------------------------------------------ #
    #  Read-only properties                                               #
    # ------------------------------------------------------------------ #

    @property
    def daily_count(self) -> int:
        with self._lock:
            self._ensure_today()
            return self._state["daily_count"]

    @property
    def daily_losses(self) -> int:
        with self._lock:
            self._ensure_today()
            return self._state.get("daily_losses", 0)

    @property
    def last_trade_time(self) -> Optional[datetime]:
        with self._lock:
            t = self._state.get("last_trade_time")
            return datetime.fromisoformat(t) if t else None

    @property
    def events(self) -> list[dict]:
        return list(self._events)   # copy for thread-safety

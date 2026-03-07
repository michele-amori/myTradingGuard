"""
UIStateWriter — writes a JSON snapshot of the dashboard state every second
to ~/.mytradingguard/ui_state.json so the native macOS app can read it.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytz

if TYPE_CHECKING:
    from config import Config
    from rules_engine import RulesEngine
    from trade_state import TradeState

UI_STATE_FILE = Path.home() / ".mytradingguard" / "ui_state.json"


class UIStateWriter:

    def __init__(self, state: "TradeState", cfg: "Config", engine: "RulesEngine"):
        self.state  = state
        self.cfg    = cfg
        self.engine = engine
        self._stop  = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._write()
            except Exception:
                pass
            self._stop.wait(1.0)

    def _write(self):
        cfg    = self.cfg
        state  = self.state
        engine = self.engine

        tz       = pytz.timezone(cfg.time_window.timezone)
        now_local = datetime.now(tz)
        now       = datetime.now()

        # ── Evaluate rules ─────────────────────────────────────────── #
        rules_out = []

        # Rule 1: Time window
        ok_tw, msg_tw = engine.check_time_window(state, cfg)
        tw = cfg.time_window
        if not tw.active:
            detail_tw = "Disabled"
        elif tw.windows:
            detail_tw = "  |  ".join(f"{w['start']}–{w['end']}" for w in tw.windows)
            detail_tw += f"  ({tw.timezone})"
        else:
            detail_tw = "No restriction"
        rules_out.append({
            "name": "Time Window",
            "active": tw.active,
            "ok": ok_tw,
            "detail": detail_tw if tw.active else "Disabled",
        })

        # Rule 2: Cooldown
        ok_cd, _ = engine.check_cooldown(state, cfg)
        cd   = cfg.cooldown
        last = state.last_trade_time
        if not cd.active:
            detail_cd = "Disabled"
        elif last:
            elapsed   = now - last
            remaining = timedelta(minutes=cd.minutes) - elapsed
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                detail_cd = f"Unlocks in {mins}m {secs}s"
            else:
                detail_cd = f"Last trade: {last.strftime('%H:%M:%S')} ✓"
        else:
            detail_cd = "No trades today"
        rules_out.append({
            "name": f"Cooldown ({cd.minutes}min)",
            "active": cd.active,
            "ok": ok_cd,
            "detail": detail_cd,
        })

        # Rule 3: Max daily trades
        ok_mt, _ = engine.check_max_trades(state, cfg)
        mt    = cfg.max_daily_trades
        count = state.daily_count
        rules_out.append({
            "name": "Max Daily Trades",
            "active": mt.active,
            "ok": ok_mt,
            "detail": f"{count} / {mt.value}" if mt.active else "Disabled",
            "progress": count,
            "progress_max": mt.value,
        })

        # Rule 4: Max daily losses
        ok_ml, _ = engine.check_max_losses(state, cfg)
        ml     = cfg.max_daily_losses
        losses = state.daily_losses
        rules_out.append({
            "name": "Max Daily Losses",
            "active": ml.active,
            "ok": ok_ml,
            "detail": f"{losses} / {ml.value}" if ml.active else "Disabled",
            "progress": losses,
            "progress_max": ml.value,
        })

        # Rule 5: Max order size (static)
        ms = cfg.max_order_size
        rules_out.append({
            "name": "Max Order Size",
            "active": ms.active,
            "ok": True,
            "detail": f"Max {ms.value} contract(s) per order" if ms.active else "Disabled",
        })

        # ── Global status ───────────────────────────────────────────── #
        all_ok = ok_tw and ok_cd and ok_mt and ok_ml
        block_reason = ""
        if not all_ok:
            for r, (ok_val, msg) in zip(
                rules_out[:4],
                [
                    (ok_tw, msg_tw),
                    (ok_cd, engine.check_cooldown(state, cfg)[1]),
                    (ok_mt, engine.check_max_trades(state, cfg)[1]),
                    (ok_ml, engine.check_max_losses(state, cfg)[1]),
                ]
            ):
                if not ok_val:
                    block_reason = msg
                    break

        # ── Events ─────────────────────────────────────────────────── #
        events_out = []
        for ev in reversed(state.events[-20:]):
            events_out.append({
                "time":   ev["ts"].strftime("%H:%M:%S"),
                "kind":   ev["kind"],
                "detail": ev["detail"],
            })

        # ── Write ───────────────────────────────────────────────────── #
        payload = {
            "timestamp":       now_local.strftime("%A %d %b %Y  %H:%M:%S"),
            "timezone":        cfg.time_window.timezone,
            "trading_blocked": not all_ok,
            "block_reason":    block_reason,
            "broker":          cfg.broker.title(),
            "broker_env":      cfg.broker_env.upper(),
            "proxy_port":      cfg.proxy_port,
            "daily_count":     count,
            "daily_losses":    losses,
            "rules":           rules_out,
            "events":          events_out,
        }

        UI_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = UI_STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(UI_STATE_FILE)   # atomic write

"""
Config — loads and validates configuration from config.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILE = Path(__file__).parent / "config.json"


@dataclass
class Config:
    # Time windows: list of {"start": "HH:MM", "end": "HH:MM"}
    time_windows: list[dict] = field(default_factory=list)
    # Timezone for time windows (pytz-compatible)
    timezone: str = "America/New_York"
    # Cooldown minutes between trades (0 = disabled)
    cooldown_minutes: int = 5
    # Maximum number of trades per day (0 = disabled)
    max_daily_trades: int = 3
    # Maximum number of losing trades per day before trading is blocked (0 = disabled)
    max_daily_losses: int = 0
    # Maximum order size in contracts (0 = disabled)
    max_order_size: int = 0
    # Broker: "tradovate" | "interactive_brokers"
    broker: str = "tradovate"
    # Broker environment: "live" | "demo"
    broker_env: str = "demo"
    # Local proxy port
    proxy_port: int = 8080
    # Play sound when an order is blocked
    sound_enabled: bool = True
    # If True, also notify when an order is allowed (green)
    notify_allowed: bool = False

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "Config":
        if not path.exists():
            raise FileNotFoundError(
                f"config.json not found at {path}. "
                "Copy config.json.example to config.json and customize it."
            )
        with open(path) as f:
            raw = json.load(f)

        cfg = cls(
            time_windows=raw.get("time_windows", []),
            timezone=raw.get("timezone", "America/New_York"),
            cooldown_minutes=int(raw.get("cooldown_minutes", 5)),
            max_daily_trades=int(raw.get("max_daily_trades", 3)),
            max_daily_losses=int(raw.get("max_daily_losses", 0)),
            max_order_size=int(raw.get("max_order_size", 0)),
            broker=raw.get("broker", "tradovate"),
            broker_env=raw.get("broker_env", "demo"),
            proxy_port=int(raw.get("proxy_port", 8080)),
            sound_enabled=bool(raw.get("sound_enabled", True)),
            notify_allowed=bool(raw.get("notify_allowed", False)),
        )
        cfg._validate()
        return cfg

    def _validate(self):
        for w in self.time_windows:
            if "start" not in w or "end" not in w:
                raise ValueError(f"Malformed time window: {w}")
        if self.broker not in ("tradovate", "interactive_brokers"):
            raise ValueError(f"Unsupported broker: {self.broker}")
        if self.broker_env not in ("live", "demo"):
            raise ValueError(f"broker_env must be 'live' or 'demo'")

    def reload(self) -> "Config":
        """Reloads configuration from file (useful for hot-reload)."""
        new = Config.load()
        self.__dict__.update(new.__dict__)
        return self

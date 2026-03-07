"""
Config — loads and validates configuration from config.json.

Each rule is stored as a nested object with an "active" flag:
  "cooldown": { "active": true, "minutes": 30 }
Setting "active": false disables the rule without changing its value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILE = Path(__file__).parent / "config.json"


# ------------------------------------------------------------------ #
#  Per-rule dataclasses                                               #
# ------------------------------------------------------------------ #

@dataclass
class TimeWindowRule:
    active: bool = True
    timezone: str = "America/New_York"
    windows: list[dict] = field(default_factory=list)


@dataclass
class CooldownRule:
    active: bool = True
    minutes: int = 30


@dataclass
class MaxDailyTradesRule:
    active: bool = True
    value: int = 3


@dataclass
class MaxDailyLossesRule:
    active: bool = True
    value: int = 2


@dataclass
class MaxOrderSizeRule:
    active: bool = True
    value: int = 2


# ------------------------------------------------------------------ #
#  Main Config                                                        #
# ------------------------------------------------------------------ #

@dataclass
class Config:
    time_window: TimeWindowRule = field(default_factory=TimeWindowRule)
    cooldown: CooldownRule = field(default_factory=CooldownRule)
    max_daily_trades: MaxDailyTradesRule = field(default_factory=MaxDailyTradesRule)
    max_daily_losses: MaxDailyLossesRule = field(default_factory=MaxDailyLossesRule)
    max_order_size: MaxOrderSizeRule = field(default_factory=MaxOrderSizeRule)

    broker: str = "tradovate"
    broker_env: str = "demo"
    proxy_port: int = 8080
    sound_enabled: bool = True
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

        rules = raw.get("rules", {})

        def _rule(key: dict, defaults: dict) -> dict:
            r = rules.get(key, {})
            return {**defaults, **r}

        tw = _rule("time_window", {"active": True, "timezone": "America/New_York", "windows": []})
        cd = _rule("cooldown",    {"active": True, "minutes": 30})
        mt = _rule("max_daily_trades",  {"active": True, "value": 3})
        ml = _rule("max_daily_losses",  {"active": True, "value": 2})
        ms = _rule("max_order_size",    {"active": True, "value": 2})

        cfg = cls(
            time_window=TimeWindowRule(
                active=bool(tw["active"]),
                timezone=str(tw.get("timezone", "America/New_York")),
                windows=list(tw.get("windows", [])),
            ),
            cooldown=CooldownRule(
                active=bool(cd["active"]),
                minutes=int(cd.get("minutes", 30)),
            ),
            max_daily_trades=MaxDailyTradesRule(
                active=bool(mt["active"]),
                value=int(mt.get("value", 3)),
            ),
            max_daily_losses=MaxDailyLossesRule(
                active=bool(ml["active"]),
                value=int(ml.get("value", 2)),
            ),
            max_order_size=MaxOrderSizeRule(
                active=bool(ms["active"]),
                value=int(ms.get("value", 2)),
            ),
            broker=raw.get("broker", "tradovate"),
            broker_env=raw.get("broker_env", "demo"),
            proxy_port=int(raw.get("proxy_port", 8080)),
            sound_enabled=bool(raw.get("sound_enabled", True)),
            notify_allowed=bool(raw.get("notify_allowed", False)),
        )
        cfg._validate()
        return cfg

    def _validate(self):
        for w in self.time_window.windows:
            if "start" not in w or "end" not in w:
                raise ValueError(f"Malformed time window: {w}")
        if self.broker not in ("tradovate", "interactive_brokers"):
            raise ValueError(f"Unsupported broker: {self.broker}")
        if self.broker_env not in ("live", "demo"):
            raise ValueError(f"broker_env must be 'live' or 'demo'")

    def reload(self) -> "Config":
        """Reloads configuration from file (hot-reload)."""
        new = Config.load()
        self.__dict__.update(new.__dict__)
        return self

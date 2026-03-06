"""
Notifier — plays system sounds on order block/allow events.
"""

from __future__ import annotations

import subprocess
import threading
from enum import Enum
from pathlib import Path


class AlertType(Enum):
    BLOCKED = "blocked"
    ALLOWED = "allowed"


_SOUNDS = {
    AlertType.BLOCKED: "/System/Library/Sounds/Basso.aiff",
    AlertType.ALLOWED: "/System/Library/Sounds/Funk.aiff",
}


class Notifier:
    def __init__(self, sound_enabled: bool = True, notify_allowed: bool = False):
        self.sound_enabled = sound_enabled
        self.notify_allowed = notify_allowed

    def blocked(self, reason: str):
        """Play block sound."""
        if self.sound_enabled:
            self._play_async(AlertType.BLOCKED)

    def allowed(self, detail: str):
        """Play allow sound — only if notify_allowed=True."""
        if self.notify_allowed and self.sound_enabled:
            self._play_async(AlertType.ALLOWED)

    def _play_async(self, alert_type: AlertType):
        t = threading.Thread(target=self._play_sound, args=(alert_type,), daemon=True)
        t.start()

    @staticmethod
    def _play_sound(alert_type: AlertType):
        sound_path = _SOUNDS.get(alert_type)
        if not sound_path or not Path(sound_path).exists():
            return
        try:
            subprocess.run(["afplay", sound_path], capture_output=True, timeout=3)
        except Exception:
            pass

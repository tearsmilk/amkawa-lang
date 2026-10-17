"""Tiny JSON settings store."""
import json

from .paths import settings_file

DEFAULTS = {
    "input_device": None,
    "output_device": None,
    "monitor_device": None,
    "monitor_enabled": False,
    "monitor_volume": 0.8,
    "input_gain": 1.0,
    "output_gain": 1.0,
    "gate_db": -50.0,
    "model_id": "kawaii",
    "overrides": {},  # model_id -> {param: value}
    "rvc_block": 0.5,
    "theme": "system",
    "tts_voice": None,
    "tts_rate": 1.0,
    "tts_pitch": 3.0,
    "tts_duck": True,
}


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        try:
            self.update(json.loads(settings_file().read_text("utf-8")))
        except Exception:
            pass

    def save(self):
        try:
            settings_file().write_text(json.dumps(self, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass

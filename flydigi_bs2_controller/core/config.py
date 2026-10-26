# flydigi_bs2_controller/core/config.py
"""
Configuration management for Flydigi BS2 / BS2 Pro controller.
Persists user preferences, active mode, and custom fan curve.
"""

from dataclasses import dataclass, field, asdict
import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_CUSTOM_CURVE: List[List[int]] = [
    [30, 1300],
    [40, 1700],
    [50, 2100],
    [60, 2600],
    [70, 3200],
    [80, 3700],
    [90, 4000],
    [100, 4000],
]


@dataclass
class AppConfig:
    cooling_mode: str = "smart"  # "smart" | "fixed"
    smart_preset: str = "silent"  # "silent" | "performance" | "custom"
    fixed_rpm: int = 2000
    gear_led: bool = True
    auto_start: bool = True
    smart_start_stop: int = 1  # 0: off, 1: instant, 2: delay
    rgb_mode: int = 6  # 0: off, 1: streamer, 2: rotate, 3: breathe, 4: pure, 5: multicolor, 6: intelligent
    custom_curve: List[List[int]] = field(default_factory=lambda: [list(item) for item in DEFAULT_CUSTOM_CURVE])


class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = AppConfig()
        self.load()

    def load(self) -> None:
        """Load configuration from JSON file, fallback to default on error."""
        if not os.path.exists(self.config_path):
            self.config = AppConfig()
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Filter unknown keys to avoid TypeError on dataclass init
            valid_keys = {f.name for f in AppConfig.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            self.config = AppConfig(**filtered)
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}, using defaults")
            self.config = AppConfig()

    def save(self) -> None:
        """Save current configuration to JSON file."""
        try:
            folder = os.path.dirname(self.config_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")

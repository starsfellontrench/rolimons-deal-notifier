from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class Config:
    discord_token: str
    poll_interval_seconds: float
    item_cache_refresh_seconds: float
    default_min_percent: float
    desktop_notifications_enabled: bool


def load_config() -> Config:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    raw = json.loads(_CONFIG_PATH.read_text()) if _CONFIG_PATH.exists() else {}

    return Config(
        discord_token=token,
        poll_interval_seconds=raw.get("poll_interval_seconds", 5.0),
        item_cache_refresh_seconds=raw.get("item_cache_refresh_seconds", 3600.0),
        default_min_percent=raw.get("default_min_percent", 5.0),
        desktop_notifications_enabled=raw.get("desktop_notifications_enabled", True),
    )

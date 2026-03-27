"""
ZUGZWANG - Configuration Manager
Handles persistent settings stored in user's AppData directory.
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import AppSettings

logger = logging.getLogger(__name__)

APP_NAME = "ZUGZWANG"
APP_VERSION = "1.0.0"
APP_AUTHOR = "ZUGZWANG"


def get_app_data_dir() -> Path:
    """Return platform-appropriate application data directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_data_dir() -> Path:
    """Return directory for exports and project files."""
    d = get_app_data_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_exports_dir() -> Path:
    d = get_data_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_projects_dir() -> Path:
    d = get_data_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_memory_db_path() -> Path:
    return get_data_dir() / "app_memory.db"


def get_logs_dir() -> Path:
    d = get_app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_screenshots_dir() -> Path:
    d = get_app_data_dir() / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


class ConfigManager:
    """
    Singleton-style settings manager.
    Reads/writes AppSettings to a JSON file in the user's AppData folder.
    """

    _instance: "ConfigManager | None" = None
    _settings_path: Path
    _settings: AppSettings

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._settings_path = get_app_data_dir() / "settings.json"
        self._settings = self._load()
        self._initialized = True

    def _load(self) -> AppSettings:
        if self._settings_path.exists():
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._merge_with_defaults(data)
            except Exception as e:
                logger.warning(f"Failed to load settings, using defaults: {e}")
        return AppSettings()

    def _merge_with_defaults(self, data: dict) -> AppSettings:
        """Merge saved settings with defaults to handle new fields after upgrades."""
        defaults = asdict(AppSettings())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        try:
            return AppSettings(**{k: defaults[k] for k in AppSettings.__dataclass_fields__})
        except Exception:
            return AppSettings()

    def save(self) -> None:
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._settings), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self._settings, k):
                setattr(self._settings, k, v)
        self.save()

    def reset(self) -> None:
        self._settings = AppSettings()
        self.save()


# Global singleton access
config_manager = ConfigManager()

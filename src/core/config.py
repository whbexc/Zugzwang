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
APP_VERSION = "1.0.6"
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

    # ── Search History ────────────────────────────────────────────────────────

    def _get_db(self):
        """Return a sqlite3 connection to app_memory.db."""
        import sqlite3
        conn = sqlite3.connect(str(get_memory_db_path()))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT,
                city TEXT,
                source TEXT,
                offer_type TEXT,
                radius INTEGER DEFAULT 25,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_saved INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        return conn

    def save_search(self, job_title: str, city: str, source: str, offer_type: str, radius: int = 25) -> None:
        """Save a search entry to history, keeping at most 10 unsaved entries."""
        try:
            conn = self._get_db()
            with conn:
                # Insert new entry
                conn.execute(
                    "INSERT INTO search_history (job_title, city, source, offer_type, radius) VALUES (?, ?, ?, ?, ?)",
                    (job_title, city, source, offer_type, radius)
                )
                # Prune: keep only 10 most recent unsaved entries
                conn.execute("""
                    DELETE FROM search_history WHERE is_saved = 0 AND id NOT IN (
                        SELECT id FROM search_history WHERE is_saved = 0
                        ORDER BY timestamp DESC LIMIT 10
                    )
                """)
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to save search history: {e}")

    def get_search_history(self) -> list:
        """Return search history rows ordered by saved first, then timestamp desc."""
        try:
            conn = self._get_db()
            cursor = conn.execute(
                "SELECT id, job_title, city, source, offer_type, radius, is_saved FROM search_history "
                "ORDER BY is_saved DESC, timestamp DESC LIMIT 20"
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.warning(f"Failed to load search history: {e}")
            return []

    def toggle_saved(self, history_id: int) -> bool:
        """Toggle is_saved for given history id. Returns new saved state."""
        try:
            conn = self._get_db()
            cursor = conn.execute("SELECT is_saved FROM search_history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return False
            new_val = 0 if row[0] else 1
            with conn:
                conn.execute("UPDATE search_history SET is_saved = ? WHERE id = ?", (new_val, history_id))
            conn.close()
            return bool(new_val)
        except Exception as e:
            logger.warning(f"Failed to toggle saved: {e}")
            return False

    def clear_unsaved_history(self) -> None:
        """Delete all unsaved search history entries."""
        try:
            conn = self._get_db()
            with conn:
                conn.execute("DELETE FROM search_history WHERE is_saved = 0")
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to clear history: {e}")

    def reset(self) -> None:
        """Resets configurations to factory defaults, preserving trial usage tracking."""
        # Backup trial data
        scraps = self._settings.trial_scraps_count
        last_date = self._settings.trial_last_reset_date
        
        # Reset to new AppSettings instance
        self._settings = AppSettings()
        
        # Restore trial data
        self._settings.trial_scraps_count = scraps
        self._settings.trial_last_reset_date = last_date
        
        self.save()


# Global singleton access
config_manager = ConfigManager()

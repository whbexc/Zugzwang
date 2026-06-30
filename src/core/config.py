"""
ZUGZWANG - Configuration Manager
Handles persistent settings stored in user's AppData directory.
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from .models import AppSettings

logger = logging.getLogger(__name__)

APP_NAME = "ZUGZWANG"
APP_VERSION = "1.1.0 Beta 2"
APP_BUILD = 2
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


def _clear_dir_contents(path: Path) -> None:
    """Delete all files and folders inside a directory, preserving the directory itself."""
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                logger.debug(f"Skipping locked cache file during cleanup: {child}")


class ConfigManager(QObject):
    """
    Singleton-style settings manager.
    Reads/writes AppSettings to a JSON file in the user's AppData folder.
    """
    history_updated = Signal()
    cache_cleanup_finished = Signal(bool, str)

    _instance: "ConfigManager | None" = None
    _settings_path: Path
    _settings: AppSettings

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._upgrade_state_reset_applied = False
        self._settings_path = get_app_data_dir() / "settings.json"
        self._settings_backup_path = get_app_data_dir() / "settings.backup.json"
        self._settings = self._load()
        if self._upgrade_state_reset_applied:
            self._save_sync()
        self._search_history_cache = []
        self._initialized = True
        
        # Initial history load in background
        from .db_worker import db_worker
        db_worker.submit(self._refresh_history_cache_sync)

    def _load(self) -> AppSettings:
        sources = [self._settings_path, self._settings_backup_path]
        last_error = None
        for path in sources:
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                previous_version = str(data.get("app_version", "") or "").strip()
                settings = self._merge_with_defaults(data)
                settings = self._reset_cached_state_for_upgrade(settings, previous_version)
                settings.app_version = APP_VERSION
                settings.app_build = APP_BUILD
                self._recover_persisted_machine_id(settings)
                return settings
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to load settings from {path.name}: {e}")

        settings = AppSettings(app_version=APP_VERSION, app_build=APP_BUILD)
        self._recover_persisted_machine_id(settings)
        if last_error:
            logger.warning("Falling back to default settings after load failure.")
        return settings

    def _merge_with_defaults(self, data: dict) -> AppSettings:
        """Merge saved settings with defaults to handle new fields after upgrades."""
        defaults = asdict(AppSettings())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        try:
            return AppSettings(**{k: defaults[k] for k in AppSettings.__dataclass_fields__})
        except Exception:
            return AppSettings()

    def _recover_persisted_machine_id(self, settings: AppSettings) -> None:
        if getattr(settings, "machine_id", ""):
            return
        try:
            path = get_app_data_dir() / "machine_id.txt"
            if path.exists():
                machine_id = path.read_text(encoding="utf-8").strip().upper()
                if len(machine_id) == 16:
                    settings.machine_id = machine_id
        except Exception as e:
            logger.warning(f"Failed to recover machine ID from disk: {e}")

    @staticmethod
    def _preserved_upgrade_state(settings: AppSettings) -> dict[str, Any]:
        return {
            "trial_scraps_count": settings.trial_scraps_count,
            "trial_last_reset_date": settings.trial_last_reset_date,
            "machine_id": settings.machine_id,
            "license_key": settings.license_key,
            "is_activated": settings.is_activated,
            "security_pin": settings.security_pin,
            "security_enabled": settings.security_enabled,
            "app_language": settings.app_language,
            "email_smtp_host": settings.email_smtp_host,
            "email_smtp_port": settings.email_smtp_port,
            "email_smtp_user": settings.email_smtp_user,
            "email_smtp_pass": settings.email_smtp_pass,
            "email_sender_profiles": list(settings.email_sender_profiles),
            "email_from_name": settings.email_from_name,
            "email_reply_to": settings.email_reply_to,
            "email_smtp_auth": settings.email_smtp_auth,
            "email_smtp_ssl": settings.email_smtp_ssl,
            "email_smtp_tls": settings.email_smtp_tls,
            "email_subject": settings.email_subject,
            "email_body": settings.email_body,
            "email_body_html": settings.email_body_html,
            "email_interval": settings.email_interval,
            "email_recipients": settings.email_recipients,
            "email_attachments": settings.email_attachments,
        }

    def _reset_cached_state_for_upgrade(self, settings: AppSettings, previous_version: str) -> AppSettings:
        previous_version = (previous_version or "").strip()
        if not previous_version or previous_version == APP_VERSION:
            return settings

        preserved = self._preserved_upgrade_state(settings)
        refreshed = AppSettings(app_version=APP_VERSION, app_build=APP_BUILD)
        for key, value in preserved.items():
            setattr(refreshed, key, value)

        self._upgrade_state_reset_applied = True
        logger.info(
            "Applied one-time cached state reset for upgrade from %s to %s.",
            previous_version,
            APP_VERSION,
        )
        _clear_dir_contents(get_logs_dir())
        _clear_dir_contents(get_screenshots_dir())
        return refreshed

    def save(self) -> None:
        from .db_worker import db_worker
        db_worker.submit(self._save_sync)

    def flush(self) -> None:
        """Synchronously persist settings to disk."""
        self._save_sync()

    def _save_sync(self) -> None:
        try:
            payload = asdict(self._settings)
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                prefix="settings_",
                suffix=".json.tmp",
                dir=str(self._settings_path.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self._settings_path)
            finally:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception:
                    pass

            try:
                shutil.copy2(self._settings_path, self._settings_backup_path)
            except Exception as backup_error:
                logger.warning(f"Failed to write settings backup: {backup_error}")
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
        from .db_worker import db_worker
        db_worker.submit(self._save_search_sync, job_title, city, source, offer_type, radius)

    def _save_search_sync(self, job_title: str, city: str, source: str, offer_type: str, radius: int = 25) -> None:
        """Internal synchronous save method called by db_worker."""
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


    def _refresh_history_cache_sync(self) -> None:
        """Internal refresh called by background worker."""
        try:
            conn = self._get_db()
            cursor = conn.execute(
                "SELECT id, job_title, city, source, offer_type, radius, is_saved FROM search_history "
                "ORDER BY is_saved DESC, timestamp DESC LIMIT 20"
            )
            self._search_history_cache = cursor.fetchall()
            conn.close()
            # Signal UI that data changed
            self.history_updated.emit()
        except Exception as e:
            logger.warning(f"Failed to refresh history cache: {e}")

    def get_search_history(self) -> list:
        """Return cached search history (non-blocking)."""
        return list(self._search_history_cache)

    def toggle_saved(self, history_id: int) -> None:
        """Toggle is_saved for given history id in background."""
        from .db_worker import db_worker
        db_worker.submit(self._toggle_saved_sync, history_id)

    def _toggle_saved_sync(self, history_id: int) -> None:
        try:
            conn = self._get_db()
            cursor = conn.execute("SELECT is_saved FROM search_history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            if row:
                new_val = 0 if row[0] else 1
                with conn:
                    conn.execute("UPDATE search_history SET is_saved = ? WHERE id = ?", (new_val, history_id))
            conn.close()
            self._refresh_history_cache_sync()
        except Exception as e:
            logger.warning(f"Failed to toggle saved: {e}")

    def clear_unsaved_history(self) -> None:
        """Delete all unsaved search history entries in background."""
        from .db_worker import db_worker
        db_worker.submit(self._clear_unsaved_history_sync)

    def _clear_unsaved_history_sync(self) -> None:
        try:
            conn = self._get_db()
            with conn:
                conn.execute("DELETE FROM search_history WHERE is_saved = 0")
            conn.close()
            self._refresh_history_cache_sync()
        except Exception as e:
            logger.warning(f"Failed to clear history: {e}")

    def clear_search_history(self) -> None:
        """Delete all search history entries synchronously."""
        self._clear_search_history_sync()

    def _clear_search_history_sync(self) -> None:
        try:
            conn = self._get_db()
            with conn:
                conn.execute("DELETE FROM search_history")
            conn.close()
            self._refresh_history_cache_sync()
        except Exception as e:
            logger.warning(f"Failed to clear all history: {e}")

    def clear_cached_app_data(self) -> None:
        """Reset stale AppData settings/cache while preserving activation and trial state."""
        preserved = self._preserved_upgrade_state(self._settings)

        try:
            if self._settings_path.exists():
                self._settings_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove cached settings file: {e}")

        self._settings = AppSettings(app_version=APP_VERSION, app_build=APP_BUILD)
        for key, value in preserved.items():
            setattr(self._settings, key, value)

        self._clear_search_history_sync()
        _clear_dir_contents(get_logs_dir())
        _clear_dir_contents(get_screenshots_dir())
        self._save_sync()

    def clear_cached_app_data_async(self) -> None:
        """Run AppData cleanup on the background DB worker."""
        from .db_worker import db_worker
        db_worker.submit(self._clear_cached_app_data_task)

    def _clear_cached_app_data_task(self) -> None:
        try:
            self.clear_cached_app_data()
            self.cache_cleanup_finished.emit(True, "")
        except Exception as e:
            logger.error(f"Cached AppData cleanup failed: {e}", exc_info=True)
            self.cache_cleanup_finished.emit(False, str(e))

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

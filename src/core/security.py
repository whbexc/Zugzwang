"""
ZUGZWANG - Security & Licensing Engine
Handles hardware fingerprinting and license validation.
"""

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path

from .config import config_manager, get_app_data_dir
from .logger import get_logger

logger = get_logger(__name__)

# Hashed security constants — raw admin secret is never stored in source.
# Override keys are machine-bound and derived from the hashed admin seed only.
_ADMIN_OVERRIDE_SEED_HASH = "b216dd4a3e0a43535b926069a969d261270205d5893e03d8b63f65f41dcb9668"
_SALT_HASH                = "4848e7c8d786a16987ec133df5b7da6e4abe69460060d099bdfd90279cd9ec96"

MAX_FREE_TRIAL_SCRAPS = 20
MAX_FREE_TRIAL_PDFS = 5
MAX_FREE_TRIAL_EMAILS = 20

class LicenseManager:
    """
    Manages application activation and hardware fingerprinting.
    """

    @staticmethod
    def _format_key(prefix: str, signature: str) -> str:
        blocks = [signature[i:i+4] for i in range(0, len(signature), 4)]
        return f"{prefix}-{'-'.join(blocks)}"

    @staticmethod
    def _normalize_key(key: str) -> str:
        return (key or "").replace("-", "").strip().upper()

    @staticmethod
    def _machine_id_path() -> Path:
        return get_app_data_dir() / "machine_id.txt"

    @staticmethod
    def _format_machine_id(raw_id: str) -> str:
        return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16].upper()

    @staticmethod
    def _emergency_machine_seed() -> str:
        computer = os.environ.get("COMPUTERNAME", "").strip()
        user = os.environ.get("USERNAME", "").strip()
        home = str(Path.home()).strip()
        seed = f"{computer}|{user}|{home}|{os.name}|{uuid.getnode()}"
        return seed or f"fallback|{os.name}|{uuid.getnode()}"

    @staticmethod
    def _get_windows_machine_guid() -> str:
        if os.name != "nt":
            return ""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
        except Exception:
            return ""

    @staticmethod
    def _load_persisted_machine_id() -> str:
        settings_mid = (getattr(config_manager.settings, "machine_id", "") or "").strip().upper()
        if settings_mid:
            return settings_mid
        path = LicenseManager._machine_id_path()
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip().upper()
                if len(value) == 16:
                    return value
        except Exception:
            logger.warning("Failed to read persisted machine ID.", exc_info=True)
        return ""

    @staticmethod
    def _persist_machine_id(machine_id: str) -> None:
        normalized = (machine_id or "").strip().upper()
        if len(normalized) != 16:
            return
        try:
            LicenseManager._machine_id_path().write_text(normalized, encoding="utf-8")
        except Exception:
            logger.warning("Failed to persist machine ID to disk.", exc_info=True)
        try:
            if getattr(config_manager.settings, "machine_id", "") != normalized:
                config_manager.update(machine_id=normalized)
                config_manager.flush()
        except Exception:
            logger.warning("Failed to persist machine ID to settings.", exc_info=True)

    @staticmethod
    def _candidate_machine_ids() -> list[str]:
        candidates: list[str] = []
        try:
            persisted = LicenseManager._load_persisted_machine_id()
            if persisted:
                candidates.append(persisted)
        except Exception:
            logger.warning("Failed loading persisted machine ID candidate.", exc_info=True)

        try:
            machine_guid = LicenseManager._get_windows_machine_guid()
            if machine_guid:
                candidates.append(LicenseManager._format_machine_id(f"{machine_guid}-{os.name}"))
        except Exception:
            logger.warning("Failed loading MachineGuid candidate.", exc_info=True)

        try:
            # Legacy fallback for customers who already received keys from older builds.
            legacy_mid = LicenseManager._format_machine_id(f"{uuid.getnode()}-{os.name}")
            if legacy_mid:
                candidates.append(legacy_mid)
        except Exception:
            logger.warning("Failed loading legacy machine ID candidate.", exc_info=True)

        try:
            emergency_mid = LicenseManager._format_machine_id(LicenseManager._emergency_machine_seed())
            if emergency_mid:
                candidates.append(emergency_mid)
        except Exception:
            logger.warning("Failed loading emergency machine ID candidate.", exc_info=True)

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                unique.append(candidate)
                seen.add(candidate)
        return unique

    @staticmethod
    def get_machine_id() -> str:
        """
        Returns a stable machine identifier for the current machine.
        Preference order:
        1. Previously persisted app machine ID
        2. Windows MachineGuid-derived ID
        3. Legacy MAC-derived fallback
        """
        try:
            candidates = LicenseManager._candidate_machine_ids()
            machine_id = candidates[0] if candidates else ""
            if not machine_id:
                machine_id = LicenseManager._format_machine_id(LicenseManager._emergency_machine_seed())
            LicenseManager._persist_machine_id(machine_id)
            return machine_id
        except Exception:
            logger.error("Machine ID generation failed; using emergency fallback.", exc_info=True)
            fallback = LicenseManager._format_machine_id(LicenseManager._emergency_machine_seed())
            try:
                LicenseManager._persist_machine_id(fallback)
            except Exception:
                logger.warning("Failed to persist emergency machine ID fallback.", exc_info=True)
            return fallback

    @staticmethod
    def generate_license_key(machine_id: str) -> str:
        """
        Server-side logic (here for dev convenience).
        Generates the valid license key for a given Machine ID.
        Format: ZUG-XXXX-XXXX-XXXX
        """
        raw_payload = f"{machine_id}{_SALT_HASH}"
        signature = hashlib.sha256(raw_payload.encode()).hexdigest()[:12].upper()
        return LicenseManager._format_key("ZUG", signature)

    @staticmethod
    def generate_admin_override_key(machine_id: str) -> str:
        """
        Generates a machine-bound admin override key for internal support/dev use.
        Format: ADM-XXXX-XXXX-XXXX
        """
        normalized_mid = (machine_id or "").strip().upper()
        raw_payload = f"ADMIN::{normalized_mid}::{_ADMIN_OVERRIDE_SEED_HASH}"
        signature = hashlib.sha256(raw_payload.encode()).hexdigest()[:12].upper()
        return LicenseManager._format_key("ADM", signature)

    @staticmethod
    def validate_license(key: str) -> bool:
        """
        Checks if the provided key matches the current machine's hardware ID.
        Also supports machine-bound internal admin override keys.
        """
        if not key or len(key) < 5:
            return False
            
        if LicenseManager.is_banned(key):
            return False
            
        clean_key = LicenseManager._normalize_key(key)
        for machine_id in LicenseManager._candidate_machine_ids():
            expected_keys = (
                LicenseManager.generate_license_key(machine_id),
                LicenseManager.generate_admin_override_key(machine_id),
            )
            if any(clean_key == LicenseManager._normalize_key(expected_key) for expected_key in expected_keys):
                LicenseManager._persist_machine_id(machine_id)
                return True

        return False

    @staticmethod
    def is_banned(key: str = "") -> bool:
        """Local ban check (can be expanded to local blacklist)."""
        return False

    @staticmethod
    def is_active() -> bool:
        """Helper to check current activation state."""
        settings = config_manager.settings
        if LicenseManager.is_banned(settings.license_key):
            return False
        if settings.is_activated:
            # Re-verify locally to prevent simple JSON manipulation
            valid = LicenseManager.validate_license(settings.license_key)
            logger.debug(f"License verification: {valid} (Key: {settings.license_key[:8]}...)")
            return valid
        logger.debug("License status: NOT ACTIVATED (Trial Mode)")
        return False

    @staticmethod
    def activate(key: str) -> bool:
        """Attempts to activate the app with the provided key."""
        if LicenseManager.validate_license(key):
            settings = config_manager.settings
            updates = {
                "license_key": key,
                "is_activated": True,
            }

            # If the last search was auto-capped by trial mode, restore the normal default.
            if (settings.last_search_max_results or 0) <= MAX_FREE_TRIAL_SCRAPS:
                updates["last_search_max_results"] = settings.default_max_results

            config_manager.update(**updates)
            config_manager.flush()
            return True
        return False

    @staticmethod
    def get_trial_status() -> dict:
        """
        Returns a dictionary containing trial usage details.
        Handles date-based reset.
        """
        is_active = LicenseManager.is_active()
        settings = config_manager.settings
        
        if is_active:
            return {
                "used": 0,
                "remaining": 999999,
                "total": 999999,
                "is_active": True
            }

        today = datetime.now().strftime("%Y-%m-%d")

        if settings.trial_last_reset_date != today:
            # New day, reset counter
            config_manager.update(
                trial_scraps_count=0,
                trial_last_reset_date=today
            )
            settings = config_manager.settings # Refresh local ref
        
        used = settings.trial_scraps_count
        remaining = max(0, MAX_FREE_TRIAL_SCRAPS - used)
        
        return {
            "used": used,
            "remaining": remaining,
            "total": MAX_FREE_TRIAL_SCRAPS,
            "is_active": False
        }

    @staticmethod
    def can_extract() -> bool:
        """Checks if the user is allowed to extract another lead."""
        if LicenseManager.is_banned(config_manager.settings.license_key):
            return False
        if LicenseManager.is_active():
            return True

    @staticmethod
    def get_trial_status() -> dict:
        """
        Returns a dictionary containing trial usage details.
        Handles date-based reset.
        """
        is_active = LicenseManager.is_active()
        settings = config_manager.settings
        
        if is_active:
            return {
                "used": 0,
                "remaining": 999999,
                "total": 999999,
                "is_active": True
            }

        today = datetime.now().strftime("%Y-%m-%d")

        if settings.trial_last_reset_date != today:
            # New day, reset counter
            config_manager.update(
                trial_scraps_count=0,
                trial_last_reset_date=today
            )
            settings = config_manager.settings # Refresh local ref
        
        used = 0
        remaining = 20
        
        return {
            "used": used,
            "remaining": remaining,
            "total": MAX_FREE_TRIAL_SCRAPS,
            "is_active": False
        }

    @staticmethod
    def can_extract() -> bool:
        """Checks if the user is allowed to extract another lead."""
        if LicenseManager.is_banned(config_manager.settings.license_key):
            return False
        if LicenseManager.is_active():
            return True
            
        status = LicenseManager.get_trial_status()
        logger.debug(f"Trial status check: {status['remaining']} remaining / {status['used']} used")
        return status["remaining"] > 0

    @staticmethod
    def record_extraction():
        """Increments the trial counter if not activated."""
        if not LicenseManager.is_active():
            current_count = config_manager.settings.trial_scraps_count
            config_manager.update(trial_scraps_count=current_count + 1)

    @staticmethod
    def get_pdf_trial_status() -> dict:
        is_active = LicenseManager.is_active()
        settings = config_manager.settings
        
        if is_active:
            return {"used": 0, "remaining": 999999, "total": 999999, "is_active": True}

        today = datetime.now().strftime("%Y-%m-%d")
        if settings.trial_pdf_last_reset_date != today:
            config_manager.update(trial_pdf_export_count=0, trial_pdf_last_reset_date=today)
            settings = config_manager.settings
        
        used = settings.trial_pdf_export_count
        remaining = max(0, MAX_FREE_TRIAL_PDFS - used)
        return {"used": used, "remaining": remaining, "total": MAX_FREE_TRIAL_PDFS, "is_active": False}

    @staticmethod
    def can_export_pdf(count: int = 1) -> bool:
        if LicenseManager.is_banned(config_manager.settings.license_key):
            return False
        if LicenseManager.is_active():
            return True
        status = LicenseManager.get_pdf_trial_status()
        return status["remaining"] >= count

    @staticmethod
    def record_pdf_export(count: int = 1):
        if not LicenseManager.is_active():
            current_count = config_manager.settings.trial_pdf_export_count
            config_manager.update(trial_pdf_export_count=current_count + count)

    @staticmethod
    def get_email_trial_status() -> dict:
        is_active = LicenseManager.is_active()
        settings = config_manager.settings
        
        if is_active:
            return {"used": 0, "remaining": 999999, "total": 999999, "is_active": True}

        today = datetime.now().strftime("%Y-%m-%d")
        if settings.trial_email_last_reset_date != today:
            config_manager.update(trial_email_count=0, trial_email_last_reset_date=today)
            settings = config_manager.settings
        
        used = settings.trial_email_count
        remaining = max(0, MAX_FREE_TRIAL_EMAILS - used)
        return {"used": used, "remaining": remaining, "total": MAX_FREE_TRIAL_EMAILS, "is_active": False}

    @staticmethod
    def can_send_email(count: int = 1) -> bool:
        if LicenseManager.is_banned(config_manager.settings.license_key):
            return False
        if LicenseManager.is_active():
            return True
        status = LicenseManager.get_email_trial_status()
        return status["remaining"] >= count

    @staticmethod
    def record_email_send(count: int = 1):
        if not LicenseManager.is_active():
            current_count = config_manager.settings.trial_email_count
            config_manager.update(trial_email_count=current_count + count)

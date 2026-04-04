"""
ZUGZWANG - Security & Licensing Engine
Handles hardware fingerprinting and license validation.
"""

import hashlib
import uuid
import os
import json
import threading
import urllib.request
from datetime import datetime
from .config import config_manager

# Hashed security constants — original values are NEVER stored in the source code or binary.
# Use hashlib.sha256(key.encode()).hexdigest() to verify/update these.
_MASTER_KEY_HASH = "30ba28554b78612623f23011379467223587ca111958661c536f6b07e1a389c4"
_SALT_HASH       = "4848e7c8d786a16987ec133df5b7da6e4abe69460060d099bdfd90279cd9ec96"


MAX_FREE_TRIAL_SCRAPS = 20

class RemoteSecurityState:
    kill_switch = False
    banned_machine_ids = set()
    banned_license_keys = set()
    _fetch_started = False

    @classmethod
    def start_fetch(cls):
        if cls._fetch_started:
            return
        cls._fetch_started = True

        def _fetch():
            # URL to raw JSON file (e.g. GitHub Gist or your own server)
            # Format: {"kill_switch": false, "banned_machine_ids": ["..."], "banned_license_keys": ["..."]}
            url = "YOUR_JSON_URL_HERE"
            if not url or url == "YOUR_JSON_URL_HERE":
                return
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    cls.kill_switch = data.get("kill_switch", False)
                    cls.banned_machine_ids = set(data.get("banned_machine_ids", []))
                    cls.banned_license_keys = set(data.get("banned_license_keys", []))
            except Exception:
                pass

        def _ping_discord():
            webhook_url = "YOUR_DISCORD_WEBHOOK_URL_HERE"
            if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
                return
            try:
                machine_id = LicenseManager.get_machine_id()
                license_key = config_manager.settings.license_key
                is_activated = config_manager.settings.is_activated
                payload = {
                    "content": None,
                    "embeds": [{
                        "title": "ZUGZWANG App Started",
                        "color": 5814783,
                        "fields": [
                            {"name": "Machine ID", "value": f"`{machine_id}`", "inline": True},
                            {"name": "License Key", "value": f"`{license_key or 'None'}`", "inline": True},
                            {"name": "Activated", "value": str(is_activated), "inline": True}
                        ]
                    }]
                }
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(payload).encode(),
                    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()
        threading.Thread(target=_ping_discord, daemon=True).start()

class LicenseManager:
    """
    Manages application activation and hardware fingerprinting.
    """

    @staticmethod
    def get_machine_id() -> str:
        """
        Generates a unique, stable fingerprint for the current machine.
        Uses the MAC address combined with the OS name.
        """
        raw_id = f"{uuid.getnode()}-{os.name}"
        return hashlib.sha256(raw_id.encode()).hexdigest()[:16].upper()

    @staticmethod
    def generate_license_key(machine_id: str) -> str:
        """
        Server-side logic (here for dev convenience).
        Generates the valid license key for a given Machine ID.
        Format: ZUG-XXXX-XXXX-XXXX
        """
        raw_payload = f"{machine_id}{_SALT_HASH}"
        signature = hashlib.sha256(raw_payload.encode()).hexdigest()[:12].upper()
        
        # Split into blocks: ZUG-ABCD-EFGH-IJKL
        blocks = [signature[i:i+4] for i in range(0, 12, 4)]
        return f"ZUG-{''.join(blocks)}"

    @staticmethod
    def validate_license(key: str) -> bool:
        """
        Checks if the provided key matches the current machine's hardware ID.
        Also supports a developer master override (verified by hash only — key never stored).
        """
        if not key or len(key) < 5:
            return False
            
        if LicenseManager.is_banned(key):
            return False
            
        # Master Bypass — compare SHA-256 hash of input, never the key itself
        if hashlib.sha256(key.strip().encode()).hexdigest() == _MASTER_KEY_HASH:
            return True
            
        machine_id = LicenseManager.get_machine_id()
        expected_key = LicenseManager.generate_license_key(machine_id)
        
        # Strip dashes and compare case-insensitively
        clean_key = key.replace("-", "").upper()
        clean_expected = expected_key.replace("-", "").upper()
        
        return clean_key == clean_expected

    @staticmethod
    def is_banned(key: str = "") -> bool:
        if RemoteSecurityState.kill_switch:
            return True
        if LicenseManager.get_machine_id() in RemoteSecurityState.banned_machine_ids:
            return True
        if key and key in RemoteSecurityState.banned_license_keys:
            return True
        return False

    @staticmethod
    def is_active() -> bool:
        """Helper to check current activation state."""
        settings = config_manager.settings
        if LicenseManager.is_banned(settings.license_key):
            return False
        if settings.is_activated:
            # Re-verify locally to prevent simple JSON manipulation
            return LicenseManager.validate_license(settings.license_key)
        return False

    @staticmethod
    def activate(key: str) -> bool:
        """Attempts to activate the app with the provided key."""
        if LicenseManager.validate_license(key):
            config_manager.update(license_key=key, is_activated=True)
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
            
        status = LicenseManager.get_trial_status()
        return status["remaining"] > 0

    @staticmethod
    def record_extraction():
        """Increments the trial counter if not activated."""
        if not LicenseManager.is_active():
            current_count = config_manager.settings.trial_scraps_count
            config_manager.update(trial_scraps_count=current_count + 1)

# Initialize remote security monitoring on import
RemoteSecurityState.start_fetch()

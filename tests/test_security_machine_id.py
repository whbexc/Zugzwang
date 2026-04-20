from unittest.mock import patch

from src.core.models import AppSettings
from src.core.security import LicenseManager


def test_get_machine_id_prefers_persisted_value():
    with patch.object(LicenseManager, "_load_persisted_machine_id", return_value="ABCDEF1234567890"), \
         patch.object(LicenseManager, "_get_windows_machine_guid", return_value=""), \
         patch.object(LicenseManager, "_persist_machine_id") as persist:
        assert LicenseManager.get_machine_id() == "ABCDEF1234567890"
        persist.assert_called_once_with("ABCDEF1234567890")


def test_validate_license_accepts_legacy_machine_id_and_persists_it():
    legacy_mid = "FACEFACEFACE123"
    key = LicenseManager.generate_license_key(legacy_mid)

    with patch.object(LicenseManager, "_candidate_machine_ids", return_value=["NEWNEWNEWNEW1234", legacy_mid]), \
         patch.object(LicenseManager, "_persist_machine_id") as persist:
        assert LicenseManager.validate_license(key) is True
        persist.assert_called_once_with(legacy_mid)


def test_load_persisted_machine_id_reads_settings_first():
    with patch("src.core.security.config_manager") as config_manager_mock, \
         patch.object(LicenseManager, "_machine_id_path") as path_mock:
        config_manager_mock.settings = AppSettings(machine_id="1234567890ABCDEF")
        assert LicenseManager._load_persisted_machine_id() == "1234567890ABCDEF"
        path_mock.assert_not_called()

"""
ZUGZWANG - Update Service
Integrates with GitHub Releases to check for and download updates.
"""

import os
import sys
import httpx
import logging
import re
import socket
from PySide6.QtCore import QObject, Signal, QThread
from ..core.config import config_manager

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^\s*v?(\d+(?:\.\d+)*)([a-zA-Z]*)\s*$")
_BUILD_RE = re.compile(r"build\s*[:#-]?\s*(\d+)", re.IGNORECASE)


def _parse_version_parts(raw: str) -> tuple[tuple[int, ...], str]:
    text = (raw or "").strip()
    match = _VERSION_RE.match(text)
    if not match:
        return (0,), ""
    numeric = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2).lower()
    return numeric, suffix


def _compare_versions(current: str, latest: str) -> int:
    """
    Compare app versions with support for developer suffixes like 1.0.9b.
    Returns:
      1  -> current is newer
      0  -> same
     -1  -> latest is newer
    Rule: same numeric base + letter suffix means the suffixed version is newer
    than the plain release, so 1.0.9b > 1.0.9.
    """
    current_num, current_suffix = _parse_version_parts(current)
    latest_num, latest_suffix = _parse_version_parts(latest)

    max_len = max(len(current_num), len(latest_num))
    current_num += (0,) * (max_len - len(current_num))
    latest_num += (0,) * (max_len - len(latest_num))

    if current_num > latest_num:
        return 1
    if current_num < latest_num:
        return -1

    if current_suffix == latest_suffix:
        return 0
    if current_suffix and not latest_suffix:
        return 1
    if latest_suffix and not current_suffix:
        return -1
    if current_suffix > latest_suffix:
        return 1
    if current_suffix < latest_suffix:
        return -1
    return 0


def _extract_release_build(release_data: dict) -> int:
    for field in ("name", "body", "tag_name"):
        text = str(release_data.get(field, "") or "")
        match = _BUILD_RE.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return 0
    return 0

class UpdateWorker(QThread):
    """Background worker for update checks and downloads."""
    check_finished = Signal(bool, str, str)  # is_available, version, download_url
    download_progress = Signal(int)
    download_finished = Signal(str)  # local_path
    error = Signal(str)

    def __init__(self, mode="check", url=None):
        super().__init__()
        self.mode = mode
        self.url = url

    def run(self):
        try:
            if self.mode == "check":
                self._check_for_updates()
            elif self.mode == "download":
                self._download_update()
        except (httpx.HTTPError, socket.gaierror, OSError) as e:
            if self.mode == "check":
                logger.info(f"Update check skipped: {e}")
                self.check_finished.emit(False, "", "")
                return
            logger.error(f"Update download error: {str(e)}")
            self.error.emit(str(e))
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            if self.mode == "check":
                self.check_finished.emit(False, "", "")
            else:
                self.error.emit(str(e))

    def _check_for_updates(self):
        from ..core.config import APP_BUILD, APP_VERSION
        s = config_manager.settings
        repo_url = s.git_repo_url
        if not repo_url or "github.com/" not in repo_url:
            self.check_finished.emit(False, "", "")
            return

        # Extract user/repo from URL
        parts = repo_url.split("github.com/")[-1].split("/")
        if len(parts) < 2:
            self.check_finished.emit(False, "", "")
            return
            
        repo_path = f"{parts[0]}/{parts[1]}".replace(".git", "")
        api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(api_url)
            if response.status_code != 200:
                self.check_finished.emit(False, "", "")
                return
                
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("vV").strip()
            latest_build = _extract_release_build(data)
            current_version = APP_VERSION.lstrip("vV").strip()
            current_build = APP_BUILD

            # Only notify when GitHub has a version strictly newer than what is installed.
            # Same version + same/older build → silent, no popup.
            if not latest_version:
                self.check_finished.emit(False, "", "")
                return

            version_cmp = _compare_versions(current_version, latest_version)
            if version_cmp > 0:
                self.check_finished.emit(False, "", "")
                return
            if version_cmp == 0 and latest_build <= current_build:
                self.check_finished.emit(False, "", "")
                return

            # Find the .exe or installer asset
            assets = data.get("assets", [])
            download_url = ""
            for asset in assets:
                if asset["name"].endswith(".exe") or asset["name"].endswith(".msi"):
                    download_url = asset["browser_download_url"]
                    break
            
            if download_url:
                display_version = latest_version
                if latest_build > 0:
                    display_version = f"{latest_version} (build {latest_build})"
                self.check_finished.emit(True, display_version, download_url)
                return
        
        self.check_finished.emit(False, "", "")

    def _download_update(self):
        target_dir = os.path.join(os.getenv("APPDATA"), "ZUGZWANG", "temp")
        os.makedirs(target_dir, exist_ok=True)
        local_path = os.path.join(target_dir, os.path.basename(self.url))
        
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            with client.stream("GET", self.url) as response:
                total = int(response.headers.get("Content-Length", 100))
                downloaded = 0
                with open(local_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.download_progress.emit(int((downloaded / total) * 100))
        
        self.download_finished.emit(local_path)

class UpdateService(QObject):
    """Facade for update operations."""
    update_available = Signal(str, str) # version, url

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None

    def check(self):
        if self.worker and self.worker.isRunning():
            return
        self.worker = UpdateWorker(mode="check")
        self.worker.check_finished.connect(self._on_check_finished)
        self.worker.start()

    def _on_check_finished(self, available, ver, url):
        if available:
            self.update_available.emit(ver, url)

    def start_download(self, url, progress_callback, finished_callback, error_callback):
        self.worker = UpdateWorker(mode="download", url=url)
        self.worker.download_progress.connect(progress_callback)
        self.worker.download_finished.connect(finished_callback)
        self.worker.error.connect(error_callback)
        self.worker.start()

    @staticmethod
    def apply_update(path):
        import subprocess
        os.startfile(path)
        sys.exit(0)

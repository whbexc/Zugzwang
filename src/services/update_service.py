"""
ZUGZWANG - Update Service
Integrates with GitHub Releases to check for and download updates.
"""

import os
import sys
import httpx
import logging
from packaging import version
from PySide6.QtCore import QObject, Signal, QThread
from ..core.config import config_manager

logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            self.error.emit(str(e))

    def _check_for_updates(self):
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
            latest_version = data.get("tag_name", "").replace("v", "")
            current_version = s.app_version.replace("v", "")
            
            if version.parse(latest_version) > version.parse(current_version):
                # Find the .exe or installer asset
                assets = data.get("assets", [])
                download_url = ""
                for asset in assets:
                    if asset["name"].endswith(".exe") or asset["name"].endswith(".msi"):
                        download_url = asset["browser_download_url"]
                        break
                
                if download_url:
                    self.check_finished.emit(True, latest_version, download_url)
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

"""
ZUGZWANG - Browser Installer Utility
Handles Playwright browser detection and installation for both
development and PyInstaller-packaged (frozen) environments.

The core problem when frozen:
  Playwright looks for browsers relative to its own package location.
  When bundled by PyInstaller, that location is inside _internal/playwright/...
  but the actual browser binaries are NOT copied there by default.

Solutions implemented here:
  1. Detect if running frozen (sys.frozen) and set PLAYWRIGHT_BROWSERS_PATH
     to point to a writable location next to the .exe
  2. Check if chromium is already installed at that location
  3. If not, run `playwright install chromium` with the correct env var set
  4. Provide a progress callback so the UI can show a setup dialog
"""

from __future__ import annotations
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

from ..core.logger import get_logger

logger = get_logger(__name__)


def get_browsers_path() -> Path:
    """
    Return the directory where Playwright browsers should be stored.

    - Frozen (.exe): next to the executable, in a 'browsers' subfolder
      so it survives updates and is user-writable.
    - Development: default Playwright cache (~/.cache/ms-playwright or
      %LOCALAPPDATA%\\ms-playwright) — don't override it.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        exe_dir = Path(sys.executable).parent
        return exe_dir / "browsers"
    # Development — return Playwright's default path
    return _playwright_default_browsers_path()


def _playwright_default_browsers_path() -> Path:
    """Return Playwright's default browser cache directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ms-playwright"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        return Path.home() / ".cache" / "ms-playwright"


def configure_browsers_path() -> None:
    """
    Set PLAYWRIGHT_BROWSERS_PATH environment variable so Playwright
    finds (or installs) browsers at our chosen location.
    Must be called BEFORE any playwright import that triggers browser lookup.
    """
    path = get_browsers_path()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
    logger.debug(f"PLAYWRIGHT_BROWSERS_PATH set to: {path}")


def is_chromium_installed() -> bool:
    """Check whether a usable Chromium executable exists."""
    browsers_path = get_browsers_path()
    if not browsers_path.exists():
        return False

    # Search for chrome.exe / chrome-headless-shell.exe / chrome under browsers_path
    search_names = [
        "chrome.exe", "chrome-headless-shell.exe",  # Windows
        "chrome", "chrome-headless-shell",           # Linux/Mac
    ]
    for name in search_names:
        matches = list(browsers_path.rglob(name))
        if matches:
            logger.debug(f"Found Chromium at: {matches[0]}")
            return True

    return False


def install_chromium(
    progress_callback: Optional[Callable[[str], None]] = None,
    finished_callback: Optional[Callable[[bool, str], None]] = None,
) -> None:
    """
    Run `playwright install chromium` in a background thread.

    Args:
        progress_callback: called with each line of stdout/stderr output
        finished_callback: called with (success: bool, message: str) when done
    """
    def _run():
        browsers_path = get_browsers_path()
        browsers_path.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

        # Find the playwright executable
        playwright_cmd = _find_playwright_executable()
        if not playwright_cmd:
            msg = (
                "Could not find the 'playwright' command.\n"
                "Please run manually in the app folder:\n\n"
                "  playwright install chromium\n\n"
                "Or install Python and run:\n"
                "  pip install playwright && playwright install chromium"
            )
            logger.error(msg)
            if finished_callback:
                finished_callback(False, msg)
            return

        cmd = [playwright_cmd, "install", "chromium"]
        logger.info(f"Running: {' '.join(cmd)}")
        logger.info(f"Browser install path: {browsers_path}")

        if progress_callback:
            progress_callback(f"Installing Chromium browser to:\n{browsers_path}\n\nThis may take a few minutes…\n")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    logger.info(f"[playwright install] {line}")
                    if progress_callback:
                        progress_callback(line + "\n")

            proc.wait()

            if proc.returncode == 0 and is_chromium_installed():
                msg = "✓ Chromium installed successfully. You can now start scraping."
                logger.info(msg)
                if finished_callback:
                    finished_callback(True, msg)
            else:
                msg = (
                    f"Installation finished but Chromium was not found "
                    f"(exit code {proc.returncode}).\n\n"
                    f"Try running manually:\n  playwright install chromium"
                )
                logger.error(msg)
                if finished_callback:
                    finished_callback(False, msg)

        except Exception as e:
            msg = f"Installation failed: {e}"
            logger.error(msg, exc_info=True)
            if finished_callback:
                finished_callback(False, msg)

    t = threading.Thread(target=_run, daemon=True, name="browser-installer")
    t.start()


def _find_playwright_executable() -> Optional[str]:
    """Locate the playwright CLI executable."""
    # 1. If frozen: look for playwright.exe next to our exe
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for candidate in ["playwright.exe", "playwright"]:
            p = exe_dir / candidate
            if p.exists():
                return str(p)
        # Also check _internal (PyInstaller ≥ 6 puts things there)
        internal = exe_dir / "_internal"
        for candidate in ["playwright.exe", "playwright"]:
            p = internal / candidate
            if p.exists():
                return str(p)

    # 2. Development: use sys.executable -m playwright (most reliable)
    return f'"{sys.executable}" -m playwright' if not getattr(sys, "frozen", False) else None

"""
ZUGZWANG - Post-Build Script
Run this AFTER `pyinstaller zugzwang.spec` to copy the Playwright
Chromium browser into the dist folder so the .exe works out of the box.

Usage:
    python build_with_browsers.py

This script:
  1. Runs pyinstaller zugzwang.spec --clean
  2. Runs playwright install chromium (if not already installed)
  3. Copies the chromium browser into dist/ZUGZWANG/browsers/
  4. Reports the final dist size
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


DIST_DIR = Path("dist") / "ZUGZWANG"
BROWSERS_DEST = DIST_DIR / "browsers"


def run(cmd: list[str], env=None) -> int:
    print(f"\n>>> {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, env=env)
    return result.returncode


def find_playwright_browsers_path() -> Path:
    """Find where Playwright installed its browsers on this machine."""
    # Try reading from Playwright's own API
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "from playwright._impl._driver import compute_driver_executable; "
             "import json, subprocess, sys; "
             "driver = compute_driver_executable(); "
             "out = subprocess.check_output([str(driver), 'print-api-json-patch'], text=True); "
             "data = json.loads(out); "
             "print(data.get('chromium', {}).get('executablePath', ''))"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            exe_path = Path(result.stdout.strip())
            # Walk up to find the ms-playwright root
            for parent in exe_path.parents:
                if parent.name == "ms-playwright" or "ms-playwright" in parent.name:
                    return parent
    except Exception:
        pass

    # Fallback: common locations
    candidates = []
    if sys.platform == "win32":
        appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        candidates = [
            appdata / "ms-playwright",
            appdata / "Programs" / "Python" / "Python314" / "Lib" / "site-packages" / "playwright" / ".local-browsers",
        ]
        # Check inside the Python env using a more robust method
        try:
            import playwright
            pw_path = Path(playwright.__file__).parent
            candidates.append(pw_path / ".local-browsers")
        except ImportError:
            pass

    else:
        candidates = [
            Path.home() / ".cache" / "ms-playwright",
            Path.home() / "Library" / "Caches" / "ms-playwright",
        ]

    for c in candidates:
        if c.exists():
            # Check it has a chromium folder
            chromiums = list(c.glob("chromium*"))
            if chromiums:
                print(f"Found browsers at: {c}")
                return c

    return None


def copy_browsers(browsers_src: Path) -> None:
    """Copy all chromium browser files into dist/ZUGZWANG/browsers/"""
    print(f"\nCopying browsers from: {browsers_src}")
    print(f"\n[OK] Bundled browsers into: {BROWSERS_DEST}")

    if BROWSERS_DEST.exists():
        shutil.rmtree(BROWSERS_DEST)
    BROWSERS_DEST.mkdir(parents=True, exist_ok=True)

    # Copy only chromium (skip firefox/webkit to save space)
    copied = 0
    for item in browsers_src.iterdir():
        if "chromium" in item.name.lower() or "ffmpeg" in item.name.lower():
            dest = BROWSERS_DEST / item.name
            print(f"  Copying {item.name}...")
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            copied += 1

    if copied == 0:
        print("  WARNING: No chromium folder found to copy!")
    else:
        print(f"  Copied {copied} browser package(s)")


def report_size(path: Path) -> None:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    print(f"\nDist folder size: {total / 1024 / 1024:.1f} MB  ({path})")


def main():
    print("=" * 60)
    print("  ZUGZWANG - Build + Bundle Script")
    print("=" * 60)

    # Step 1: Build the .exe
    rc = run([sys.executable, "-m", "PyInstaller", "zugzwang.spec", "--clean", "--noconfirm"])
    if rc != 0:
        print(f"\nERROR: PyInstaller failed with code {rc}")
        sys.exit(rc)

    if not DIST_DIR.exists():
        print(f"\nERROR: Expected dist folder not found: {DIST_DIR}")
        sys.exit(1)

    print(f"\n[OK] Build complete: {DIST_DIR}")

    # Step 2: Ensure browsers are installed locally
    print("\nChecking for Playwright Chromium browser...")
    browsers_src = find_playwright_browsers_path()

    if browsers_src is None:
        print("\nChromium not found locally. Running: playwright install chromium")
        rc = run([sys.executable, "-m", "playwright", "install", "chromium"])
        if rc != 0:
            print("WARNING: playwright install chromium failed. Run it manually.")
        browsers_src = find_playwright_browsers_path()

    # Step 3: Copy browsers into dist
    if browsers_src and browsers_src.exists():
        copy_browsers(browsers_src)
        print("\n[OK] Browsers bundled into dist folder")
    else:
        print("\nWARNING: Could not locate browser files to bundle.")
        print("The app will prompt users to install the browser on first run.")
        print("Alternatively, run manually:")
        print(f"  xcopy /E /I \"%LOCALAPPDATA%\\ms-playwright\\chromium*\" \"{BROWSERS_DEST}\"")

    # Step 4: Also copy the playwright driver
    _copy_playwright_driver()

    report_size(DIST_DIR)

    print("\n" + "=" * 60)
    print("  DONE")
    print(f"  Installer: {DIST_DIR / 'ZUGZWANG.exe'}")
    print("  Run: makensis installer.nsi  (to build Setup.exe)")
    print("=" * 60)


def _copy_playwright_driver():
    """Copy playwright's Node.js driver into dist so CLI works frozen."""
    try:
        import playwright
        pw_dir = Path(playwright.__file__).parent
        driver_dir = pw_dir / "driver"
        if not driver_dir.exists():
            return

        dest = DIST_DIR / "_internal" / "playwright" / "driver"
        if dest.exists():
            return  # PyInstaller already included it

        print(f"\nCopying Playwright driver from {driver_dir}...")
        shutil.copytree(driver_dir, dest, dirs_exist_ok=True)
        print("  [OK] Playwright driver copied")
    except Exception as e:
        print(f"  Note: Could not copy Playwright driver: {e}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# ZUGZWANG macOS Standalone Package Builder
# Usage: ./scripts/build_macos.sh

set -e

echo "=========================================================="
echo "    ZUGZWANG — Building macOS Application Bundle (.app)"
echo "=========================================================="

# 1. Clean previous builds
rm -rf build dist/ZUGZWANG.app dist/ZUGZWANG_macOS_*.zip

# 2. Build application bundle using PyInstaller
echo "[1/4] Running PyInstaller with zugzwang.spec..."
pyinstaller zugzwang.spec --clean

# 3. Inject Chromium browser into .app bundle
echo "[2/4] Injecting Playwright Chromium into ZUGZWANG.app..."
python3 -c "
import shutil
from pathlib import Path
from build_with_browsers import find_playwright_browsers_path

app_browsers = Path('dist') / 'ZUGZWANG.app' / 'Contents' / 'MacOS' / 'browsers'
src = find_playwright_browsers_path()
if src and src.exists():
    if app_browsers.exists():
        shutil.rmtree(app_browsers)
    app_browsers.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if 'chromium' in item.name.lower():
            shutil.copytree(item, app_browsers / item.name, dirs_exist_ok=True)
    print(f'   -> Bundled Chromium into {app_browsers}')
else:
    print('   -> Warning: Chromium browser not found!')
"

# 4. Create distributable archive
echo "[3/4] Creating macOS distributable archive..."
cd dist
codesign --force --deep --sign - ZUGZWANG.app || true
zip -r -y "ZUGZWANG_macOS_1.1.0 Beta5.1.zip" ZUGZWANG.app
cd ..

echo "=========================================================="
echo "[SUCCESS] Built macOS package: dist/ZUGZWANG_macOS_1.1.0 Beta5.1.zip"
echo "=========================================================="

# 1.1.0 Beta5.1

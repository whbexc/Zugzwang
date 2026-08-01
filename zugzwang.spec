# -*- mode: python ; coding: utf-8 -*-
# ZUGZWANG - PyInstaller Build Spec
# Build with: pyinstaller zugzwang.spec

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Resolve icon path absolutely so it works regardless of working directory
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC is PyInstaller built-in)
ICON_PATH = os.path.join(SPEC_DIR, 'assets', 'icon.icns' if sys.platform == 'darwin' else 'icon.ico')

# Collect Playwright data files (JS/JSON config, not browser binaries)
datas = []
try:
    datas += collect_data_files('playwright', includes=['**/*.js', '**/*.json'])
except Exception:
    pass  # Playwright data collection is optional

# PySide6 translations & resources
try:
    datas += collect_data_files('PySide6', includes=['**/*.qm', '**/*.qmltypes'])
except Exception:
    pass

# Application Assets (Fonts, Icons, etc.)
datas += [
    ('src/ui/assets', 'src/ui/assets'),
    ('assets', 'assets'),
]

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'playwright',
    'playwright.async_api',
    # NOTE: playwright._impl._api_types was removed in Playwright >= 1.30
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'sqlite3',
    'json',
    'csv',
    'asyncio',
    'threading',
]

hiddenimports += collect_submodules('src')

a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZUGZWANG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window for release builds
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,         # Absolute path
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='ZUGZWANG',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ZUGZWANG.app',
        icon=ICON_PATH,
        bundle_identifier='com.zugzwang.app',
        info_plist={
            'CFBundleName': 'ZUGZWANG',
            'CFBundleDisplayName': 'ZUGZWANG',
            'CFBundleVersion': '1.1.0',
            'CFBundleShortVersionString': '1.1.0 Beta 3',
            'NSHighResolutionCapable': 'True',
        },
    )


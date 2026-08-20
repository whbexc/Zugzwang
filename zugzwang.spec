# -*- mode: python ; coding: utf-8 -*-
# ZUGZWANG - PyInstaller Build Spec
# Build with: pyinstaller zugzwang.spec

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Resolve icon path absolutely so it works regardless of working directory
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC is PyInstaller built-in)
if SPEC_DIR not in sys.path:
    sys.path.insert(0, SPEC_DIR)

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

# Application Assets & Source Tree (Fonts, Icons, UI, Modules, etc.)
datas += [
    ('src/ui/assets', 'src/ui/assets'),
    ('assets', 'assets'),
    ('src', 'src'),
]

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'playwright',
    'playwright.async_api',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'sqlite3',
    'json',
    'csv',
    'asyncio',
    'threading',
    'httpx',
    'bs4',
    'pypdf',
    'reportlab',
    'psutil',
    # Explicitly list all src modules to prevent missing module errors
    'src',
    'src.changelog',
    'src.diagnostics',
    'src.core',
    'src.core.config',
    'src.core.models',
    'src.core.events',
    'src.core.security',
    'src.core.logger',
    'src.core.db_worker',
    'src.core.i18n',
    'src.services',
    'src.services.email_extractor',
    'src.services.aubiplus_scraper',
    'src.services.update_service',
    'src.services.maps_scraper',
    'src.services.azubiyo_scraper',
    'src.services.ausbildung_scraper',
    'src.services.browser',
    'src.services.export_service',
    'src.services.website_crawler',
    'src.services.orchestrator',
    'src.services.browser_installer',
    'src.services.jobsuche_scraper',
    'src.services.jobsuche_api',
    'src.services.import_service',
    'src.ui',
    'src.ui.main_window',
    'src.ui.captcha_dialog',
    'src.ui.theme',
    'src.ui.icons',
    'src.ui.settings_page',
    'src.ui.shortcut_dialog',
    'src.ui.update_dialog',
    'src.ui.whats_new_dialog',
    'src.ui.security_overlay',
    'src.ui.event_bridge',
    'src.ui.load_leads_dialog',
    'src.ui.dashboard_page',
    'src.ui.edit_page',
    'src.ui.monitor_page',
    'src.ui.search_page',
    'src.ui.email_sender_page',
    'src.ui.toast_manager',
    'src.ui.components',
    'src.ui.stylesheet',
    'src.ui.log_viewer_page',
    'src.ui.activation_dialog',
    'src.ui.results_page',
    'src.utils',
    'src.utils.win32_patch',
    'src.utils.db_worker',
]

try:
    hiddenimports += collect_submodules('src')
except Exception:
    pass


a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR, os.path.join(SPEC_DIR, 'src')],
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
            'CFBundleShortVersionString': '1.1.0 Beta5.1',
            'NSHighResolutionCapable': 'True',
        },
    )


# 1.1.0 Beta5.1

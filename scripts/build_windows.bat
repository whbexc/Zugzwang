@echo off
REM ZUGZWANG Windows Standalone Installer Builder
REM Usage: scripts\build_windows.bat

echo ==========================================================
echo     ZUGZWANG -- Building Windows Setup Installer (.exe)
echo ==========================================================

REM 1. Clean previous builds
if exist build rmdir /s /q build
if exist dist\ZUGZWANG rmdir /s /q dist\ZUGZWANG

REM 2. Build standalone package and inject Chromium
echo [1/3] Running build_with_browsers.py...
python build_with_browsers.py
if %errorlevel% neq 0 (
    echo [ERROR] Python build failed.
    exit /b %errorlevel%
)

REM 3. Try building with NSIS first, fallback to InnoSetup
echo [2/3] Compiling Windows Installer...
where makensis >nul 2>nul
if %errorlevel% equ 0 (
    echo -> Found NSIS compiler. Building NSIS installer...
    makensis installer.nsi
) else (
    where iscc >nul 2>nul
    if %errorlevel% equ 0 (
        echo -> Found InnoSetup compiler. Building InnoSetup installer...
        iscc installer.iss
    ) else (
        echo [WARNING] Neither NSIS (makensis) nor InnoSetup (iscc) found in PATH!
        echo Please install NSIS (https://nsis.sourceforge.io/) or InnoSetup.
        exit /b 1
    )
)

echo ==========================================================
echo [SUCCESS] Windows installer created successfully!
echo ==========================================================

# 1.1.0 Beta5

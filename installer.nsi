; ZUGZWANG - NSIS Installer Script
; Produces a professional Windows Setup.exe installer
; Requires NSIS 3.x: https://nsis.sourceforge.io/
; Build: makensis installer.nsi

!define APP_NAME "ZUGZWANG"
!define APP_VERSION "1.0.94"
!define APP_PUBLISHER "ZUGZWANG"
!define APP_EXE "ZUGZWANG.exe"
!define APP_GUID "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
!define DIST_DIR "dist\ZUGZWANG"

; Modern UI
!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "${APP_NAME}"
Caption "${APP_NAME} Installer"
OutFile "ZUGZWANG_Setup_v${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "ZUGZWANG Installer"

; Metadata
VIProductVersion "1.0.9.1"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "Copyright 2024 ${APP_PUBLISHER}"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"

; Custom Branding Images
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "assets\wizard.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "assets\header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "assets\header.bmp"
!define MUI_HEADERIMAGE_RIGHT

!define MUI_WELCOMEPAGE_TITLE "Install ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT "${APP_NAME} installs a complete Windows workspace for scraping, lead enrichment, and outreach.$\r$\n$\r$\nYou will get:$\r$\n• Multi-source search and scraping$\r$\n• A live runtime monitor$\r$\n• Results review and export tools$\r$\n• Built-in SMTP outreach workflow$\r$\n$\r$\nClick Next to continue."
!define MUI_LICENSEPAGE_TEXT_TOP "Review the license terms before installing ${APP_NAME}."
!define MUI_DIRECTORYPAGE_TEXT_TOP "Choose where ${APP_NAME} should be installed."
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "Install location"
!define MUI_FINISHPAGE_TITLE "${APP_NAME} is ready"
!define MUI_FINISHPAGE_TEXT "${APP_NAME} has been installed successfully.$\r$\n$\r$\nYou can launch the app now or close the installer."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_NAME}"
!define MUI_FINISHPAGE_LINK "Open the GitHub project"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/whbexc/Zugzwang"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Open local release notes"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "docs\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "German"

; ── Install Section ───────────────────────────────────────────────────────────
Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  
  ; Copy all application files from PyInstaller dist
  File /r "${DIST_DIR}\*.*"
  
  ; Copy README
  File "docs\README.txt"
  
  ; Create Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
    "$INSTDIR\Uninstall.exe"
  
  ; Desktop shortcut
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  
  ; Registry entries
  WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\${APP_NAME}" "Version" "${APP_VERSION}"
  
  ; Add/Remove Programs entry
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "DisplayVersion" "${APP_VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}" \
    "NoRepair" 1
  
  ; Write uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Uninstall Section ─────────────────────────────────────────────────────────
Section "Uninstall"
  ; Remove files
  RMDir /r "$INSTDIR"
  
  ; Remove shortcuts
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  
  ; Remove registry keys
  DeleteRegKey HKCU "Software\${APP_NAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_GUID}"
SectionEnd

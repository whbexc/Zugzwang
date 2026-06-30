; ZUGZWANG - Inno Setup Installer
; Build with:
;   iscc installer.iss

#define AppName "ZUGZWANG"
#define AppVersion "1.1.0 Beta 2"
#define AppPublisher "ZUGZWANG"
#define AppExeName "ZUGZWANG.exe"
#define AppId "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
#define DistDir "dist\ZUGZWANG"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/whbexc/Zugzwang
AppSupportURL=https://github.com/whbexc/Zugzwang
AppUpdatesURL=https://github.com/whbexc/Zugzwang
DefaultDirName={autopf64}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=ZUGZWANG_Setup_v{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
DisableProgramGroupPage=yes
LicenseFile=docs\LICENSE.txt
InfoBeforeFile=docs\README.txt
WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\header.bmp
ChangesAssociations=no
ChangesEnvironment=no
CloseApplications=yes
CloseApplicationsFilter=ZUGZWANG.exe
RestartApplications=no
VersionInfoVersion=1.1.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion=1.1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "docs\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autoprograms}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKLM; Subkey: "Software\{#AppName}"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "Software\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletevalue

[Messages]
WelcomeLabel1=Install {#AppName}
WelcomeLabel2=ZUGZWANG installs a premium Windows workspace for lead generation, recruitment research, and outreach.%n%nIncluded in this setup:%n- Multi-source search and scraping%n- Live runtime monitor%n- Results review and export%n- Built-in SMTP outreach%n%nClick Next to continue.
WizardReady=Ready to install {#AppName}
FinishedHeadingLabel={#AppName} is ready
FinishedLabelNoIcons={#AppName} has been installed successfully.%n%nLaunch the app now or close the installer and start later from the desktop or Start menu.
SelectDirLabel3=Choose where {#AppName} should be installed.

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.AutoSize := False;
  WizardForm.WelcomeLabel2.Width := WizardForm.WelcomeLabel2.Width + ScaleX(20);
  WizardForm.WelcomeLabel2.Height := ScaleY(170);
end;

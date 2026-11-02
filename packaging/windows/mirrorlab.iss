; Inno Setup script. Build with:
;   iscc /DAppVersion=2.2.0 packaging\windows\mirrorlab.iss
; after `pyinstaller packaging\mirrorlab.spec`. Output: dist\MirrorLab-<version>-windows-setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3B2C9A-4D1E-4C8B-9A57-2E1D7B6A0F31}
AppName=MirrorLab
AppVersion={#AppVersion}
AppPublisher=TrinaxCode
AppPublisherURL=https://github.com/TrinaxCode/mirrorlab
AppSupportURL=https://github.com/TrinaxCode/mirrorlab/issues
AppUpdatesURL=https://github.com/TrinaxCode/mirrorlab/releases
DefaultDirName={autopf}\MirrorLab
DefaultGroupName=MirrorLab
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=MirrorLab-{#AppVersion}-windows-setup
SetupIconFile=..\icons\mirrorlab.ico
UninstallDisplayIcon={app}\MirrorLab.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\MirrorLab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MirrorLab"; Filename: "{app}\MirrorLab.exe"
Name: "{autodesktop}\MirrorLab"; Filename: "{app}\MirrorLab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MirrorLab.exe"; Description: "{cm:LaunchProgram,MirrorLab}"; Flags: nowait postinstall skipifsilent

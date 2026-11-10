#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{EE5820C6-EB67-43CE-A24C-20EE9DA58DB2}
AppName=DTL Document Processor
AppVersion={#AppVersion}
AppPublisher=DTL Document Processor
DefaultDirName={localappdata}\Programs\DTL Document Processor
DefaultGroupName=DTL Document Processor
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\Build\Windows\Installer
OutputBaseFilename=DTL-Document-Processor-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DTL-Document-Processor.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\Build\Windows\dist\DTL-Document-Processor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DTL Document Processor"; Filename: "{app}\DTL-Document-Processor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\DTL Document Processor"; Filename: "{app}\DTL-Document-Processor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\DTL-Document-Processor.exe"; Description: "Open DTL Document Processor"; Flags: nowait postinstall skipifsilent

; No workspace paths in [Files] or [UninstallDelete]. Records survive uninstall.

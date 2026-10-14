#define AppVersion "0.5"
[Setup]
AppId={{5F1C5C9C-BCF7-49D7-9208-F14D2072C61A}
AppName=Sax Cover Studio
AppVersion={#AppVersion}
AppVerName=Sax Cover Studio Beta V{#AppVersion}
AppPublisher=Rex Mu | RexFactory
VersionInfoVersion=0.5.0.0
DefaultDirName={localappdata}\Programs\Sax Cover Studio
DefaultGroupName=Sax Cover Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\dist\installer
OutputBaseFilename=SaxCoverStudio-Setup-BetaV{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\app-icon.ico
UninstallDisplayIcon={app}\SaxCoverStudio.exe
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\SaxCoverStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Sax Cover Studio"; Filename: "{app}\SaxCoverStudio.exe"; AppUserModelID: "SaxCoverStudio.Desktop"
Name: "{autodesktop}\Sax Cover Studio"; Filename: "{app}\SaxCoverStudio.exe"; AppUserModelID: "SaxCoverStudio.Desktop"; Tasks: desktopicon
[Run]
Filename: "{app}\SaxCoverStudio.exe"; Description: "Launch Sax Cover Studio"; Flags: nowait postinstall skipifsilent

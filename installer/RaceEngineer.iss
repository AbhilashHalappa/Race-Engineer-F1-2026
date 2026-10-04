#define MyAppName "Race Engineer"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Race Engineer Project"
#define MyAppExeName "RaceEngineer.exe"

[Setup]
AppId={{86CA6503-B221-4D94-91AF-5A17B73941F2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\RaceEngineer
DefaultGroupName=Race Engineer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=RaceEngineer_Stable_V2_RC3_Setup_V{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\brand\race_engineer.ico
WizardImageFile=..\assets\brand\installer_wizard.bmp
WizardSmallImageFile=..\assets\brand\installer_small.bmp
VersionInfoVersion=2.0.0.3
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Race Engineer Stable V2
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=2.0.0 RC3
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\RaceEngineer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "settings\*;user_data\*;recordings\*;analysis\*;logs\*;references\*;maps\*;voices\*"

Source: "..\dist\RaceEngineer\maps\*"; DestDir: "{app}\maps"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Dirs]
Name: "{app}\settings"
Name: "{app}\user_data"
Name: "{app}\voices"
Name: "{app}\recordings"
Name: "{app}\analysis"
Name: "{app}\logs"
Name: "{app}\references"
Name: "{app}\maps"
Name: "{app}\logs\ptt"

[Icons]
Name: "{autoprograms}\Race Engineer"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\brand\race_engineer.ico"
Name: "{autoprograms}\Race Engineer Setup"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--setup"; WorkingDir: "{app}"; IconFilename: "{app}\assets\brand\race_engineer.ico"
Name: "{autodesktop}\Race Engineer"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\brand\race_engineer.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--setup"; Description: "Run first-time setup"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Race Engineer"" program=""{app}\{#MyAppExeName}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveRaceEngineerFirewall"; Check: IsAdminLoggedOn

[UninstallDelete]
; Deliberately preserve user_data, downloaded voices, recordings, settings and references on uninstall.
Type: filesandordirs; Name: "{app}\_internal"

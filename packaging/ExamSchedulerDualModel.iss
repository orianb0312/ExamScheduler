#define AppName "ExamScheduler"
#define AppVersion "3.4.2"
#ifndef SourceRoot
  #define SourceRoot "..\dist\ExamSchedulerInstaller\payload"
#endif
#ifndef OutputRoot
  #define OutputRoot "..\dist"
#endif

[Setup]
AppId={{4B9F8F27-98E7-4E1F-9D02-2AC7201D7E54}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ExamScheduler
DefaultDirName={localappdata}\ExamScheduler
DefaultGroupName=ExamScheduler
DisableProgramGroupPage=yes
SetupIconFile={#SourceRoot}\app\src\ui\assets\exam_scheduler.ico
UninstallDisplayIcon={app}\app\src\ui\assets\exam_scheduler.ico
OutputDir={#OutputRoot}
OutputBaseFilename=ExamScheduler-Setup-Offline-DualModel-v3.4.2
DiskSpanning=yes
DiskSliceSize=2100000000
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayName=ExamScheduler

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "recommended"; Description: "Recommended - Llama 3.1 8B, best reasoning"
Name: "lightweight"; Description: "Lightweight - Qwen3 4B, smaller install"
Name: "both"; Description: "Install both local AI models"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "app"; Description: "ExamScheduler application, Python runtime, libraries, documentation, and Ollama"; Types: recommended lightweight both custom; Flags: fixed
Name: "models\llama"; Description: "Recommended model: Llama3.1 8B q4_K_M (~4.9 GB)"; Types: recommended both custom; ExtraDiskSpaceRequired: 4920756170
Name: "models\qwen"; Description: "Lightweight model: Qwen3 4B (~2.5 GB)"; Types: lightweight both custom; ExtraDiskSpaceRequired: 2497298432

[Files]
Source: "{#SourceRoot}\app\*"; DestDir: "{app}\app"; Components: app; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\runtime\python\*"; DestDir: "{app}\runtime\python"; Components: app; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\wheelhouse\*"; DestDir: "{app}\wheelhouse"; Components: app; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\scripts\install_embedded.ps1"; DestDir: "{app}"; Components: app; Flags: ignoreversion
Source: "{#SourceRoot}\scripts\verify_offline_install.ps1"; DestDir: "{app}"; Components: app; Flags: ignoreversion
Source: "{#SourceRoot}\vendor\ollama\ollama.exe"; DestDir: "{app}\ollama"; Components: app; Flags: ignoreversion
Source: "{#SourceRoot}\models\llama\*"; DestDir: "{app}\ollama\models"; Components: models\llama; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\models\qwen\*"; DestDir: "{app}\ollama\models"; Components: models\qwen; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ExamScheduler"; Filename: "{app}\Start-ExamScheduler.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app\src\ui\assets\exam_scheduler.ico"
Name: "{autodesktop}\ExamScheduler"; Filename: "{app}\Start-ExamScheduler.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app\src\ui\assets\exam_scheduler.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_embedded.ps1"" -InstallRoot ""{app}"" -ModelName ""{code:GetSelectedModelName}"" -SkipShortcut"; StatusMsg: "Configuring bundled Python environment and offline AI model..."; Flags: runhidden waituntilterminated
Filename: "{app}\Start-ExamScheduler.cmd"; Description: "Launch ExamScheduler"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: files; Name: "{app}\Start-ExamScheduler.ps1"
Type: files; Name: "{app}\Start-ExamScheduler.cmd"

[Code]
function GetSelectedModelName(Param: String): String;
begin
  if WizardIsComponentSelected('models\qwen') and not WizardIsComponentSelected('models\llama') then
    Result := 'qwen3:4b'
  else
    Result := 'llama3.1:8b-instruct-q4_K_M';
end;

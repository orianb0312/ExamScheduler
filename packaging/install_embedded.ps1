param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\ExamScheduler",
    [string]$ModelName = "llama3.1:8b-instruct-q4_K_M",
    [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$AppDir = Join-Path $InstallRoot "app"
$VenvDir = Join-Path $InstallRoot ".venv"
$PythonExe = Join-Path $InstallRoot "runtime\python\python.exe"
$WheelhouseDir = Join-Path $InstallRoot "wheelhouse"
$OllamaExe = Join-Path $InstallRoot "ollama\ollama.exe"
$OllamaModelsDir = Join-Path $InstallRoot "ollama\models"
$LaunchPs1 = Join-Path $InstallRoot "Start-ExamScheduler.ps1"
$LaunchCmd = Join-Path $InstallRoot "Start-ExamScheduler.cmd"
$IconPath = Join-Path $AppDir "src\ui\assets\exam_scheduler.ico"

if (-not (Test-Path -LiteralPath $AppDir)) {
    throw "Installed app directory is missing: $AppDir"
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Bundled Python runtime is missing: $PythonExe"
}
if (-not (Test-Path -LiteralPath $WheelhouseDir)) {
    throw "Bundled wheelhouse is missing: $WheelhouseDir"
}
if (-not (Test-Path -LiteralPath $OllamaExe)) {
    throw "Bundled Ollama executable is missing: $OllamaExe"
}
if (-not (Test-Path -LiteralPath $OllamaModelsDir)) {
    throw "Bundled Ollama model store is missing: $OllamaModelsDir"
}

Write-Host "Creating local Python environment..."
if (Test-Path -LiteralPath $VenvDir) {
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
}
& $PythonExe -m venv $VenvDir

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment was not created correctly: $VenvPython"
}

Write-Host "Installing Python packages from bundled wheelhouse..."
& $VenvPython -m pip install --no-index --find-links $WheelhouseDir -r (Join-Path $AppDir "requirements-runtime.txt")

[Environment]::SetEnvironmentVariable("EXAMSCHEDULER_OLLAMA_MODEL", $ModelName, "User")
[Environment]::SetEnvironmentVariable("EXAMSCHEDULER_OLLAMA_PATH", $OllamaExe, "User")
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $OllamaModelsDir, "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")

@"
`$env:EXAMSCHEDULER_OLLAMA_MODEL = "$ModelName"
`$env:EXAMSCHEDULER_OLLAMA_PATH = "$OllamaExe"
`$env:OLLAMA_MODELS = "$OllamaModelsDir"
`$env:OLLAMA_NO_CLOUD = "1"
`$app = Join-Path `$PSScriptRoot "app\gui_main.py"
`$pythonw = Join-Path `$PSScriptRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath `$pythonw)) {
    `$pythonw = Join-Path `$PSScriptRoot ".venv\Scripts\python.exe"
}
& `$pythonw `$app
"@ | Set-Content -LiteralPath $LaunchPs1 -Encoding ASCII

@"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-ExamScheduler.ps1"
"@ | Set-Content -LiteralPath $LaunchCmd -Encoding ASCII

if (-not $SkipShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ($desktop) {
        $shortcutPath = Join-Path $desktop "ExamScheduler.lnk"
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $LaunchCmd
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Description = "Launch ExamScheduler"
        if (Test-Path -LiteralPath $IconPath) {
            $shortcut.IconLocation = "$IconPath,0"
        }
        $shortcut.Save()
    }
}

Write-Host "Install configuration complete."

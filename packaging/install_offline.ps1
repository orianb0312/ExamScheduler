param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\ExamScheduler",
    [string]$ModelName = "llama3.1:8b-instruct-q4_K_M",
    [switch]$SkipOllamaInstall,
    [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"

$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceAppDir = Join-Path $BundleRoot "app"
$WheelhouseDir = Join-Path $BundleRoot "wheelhouse"
$VendorDir = Join-Path $BundleRoot "vendor"
$PythonInstaller = Join-Path $VendorDir "python\python-installer.exe"
$OllamaInstaller = Join-Path $VendorDir "ollama\OllamaSetup.exe"
$BundledOllamaModels = Join-Path $VendorDir "ollama\models"

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$AppDir = Join-Path $InstallRoot "app"
$VenvDir = Join-Path $InstallRoot ".venv"
$LaunchPs1 = Join-Path $InstallRoot "Start-ExamScheduler.ps1"
$LaunchCmd = Join-Path $InstallRoot "Start-ExamScheduler.cmd"

function Copy-Directory {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [switch]$Mirror
    )
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $copyMode = if ($Mirror) { "/MIR" } else { "/E" }
    robocopy $Source $Destination $copyMode /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed while copying $Source to $Destination. Exit code: $LASTEXITCODE"
    }
}

function Resolve-Python {
    $localPython = Join-Path $InstallRoot "Python\python.exe"
    if (Test-Path -LiteralPath $localPython) {
        return $localPython
    }

    if (Test-Path -LiteralPath $PythonInstaller) {
        $pythonTarget = Join-Path $InstallRoot "Python"
        New-Item -ItemType Directory -Path $pythonTarget -Force | Out-Null
        Write-Host "Installing bundled Python runtime..."
        $arguments = @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=0",
            "Include_launcher=0",
            "Include_test=0",
            "SimpleInstall=1",
            "TargetDir=`"$pythonTarget`""
        )
        Start-Process -FilePath $PythonInstaller -ArgumentList $arguments -Wait
        if (Test-Path -LiteralPath $localPython) {
            return $localPython
        }
    }

    $pythonOnPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonOnPath) {
        return $pythonOnPath.Source
    }

    throw "Python was not found. Include vendor\python\python-installer.exe in the bundle or install Python before running this script."
}

if (-not (Test-Path -LiteralPath $SourceAppDir)) {
    throw "Bundle is missing the app directory: $SourceAppDir"
}
if (-not (Test-Path -LiteralPath $WheelhouseDir)) {
    throw "Bundle is missing the wheelhouse directory: $WheelhouseDir"
}

Write-Host "Installing ExamScheduler to $InstallRoot..."
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
Copy-Directory -Source $SourceAppDir -Destination $AppDir -Mirror

$PythonExe = Resolve-Python
Write-Host "Creating virtual environment..."
& $PythonExe -m venv $VenvDir

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment was not created correctly: $VenvPython"
}

Write-Host "Installing Python packages from local wheelhouse..."
& $VenvPython -m pip install --no-index --find-links $WheelhouseDir -r (Join-Path $AppDir "requirements-runtime.txt")

if (-not $SkipOllamaInstall -and (Test-Path -LiteralPath $OllamaInstaller)) {
    $existingOllama = Get-Command ollama -ErrorAction SilentlyContinue
    $localOllama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (-not $existingOllama -and -not (Test-Path -LiteralPath $localOllama)) {
        Write-Host "Starting bundled Ollama installer..."
        Start-Process -FilePath $OllamaInstaller -Wait
    }
}

if (Test-Path -LiteralPath $BundledOllamaModels) {
    $targetModels = Join-Path $env:USERPROFILE ".ollama\models"
    Write-Host "Copying bundled Ollama models to $targetModels..."
    Copy-Directory -Source $BundledOllamaModels -Destination $targetModels
}

[Environment]::SetEnvironmentVariable("EXAMSCHEDULER_OLLAMA_MODEL", $ModelName, "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")

@"
`$env:EXAMSCHEDULER_OLLAMA_MODEL = "$ModelName"
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
        $shortcut.Save()
    }
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Launch with: $LaunchCmd"
Write-Host "Optional verification: powershell -ExecutionPolicy Bypass -File `"$BundleRoot\verify_offline_install.ps1`" -InstallRoot `"$InstallRoot`""

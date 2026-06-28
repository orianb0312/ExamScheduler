param(
    [string]$OutputDir = "dist\ExamScheduler-offline",
    [string]$RuntimeRequirements = "requirements-runtime.txt",
    [string]$ModelName = "llama3.1:8b-instruct-q4_K_M",
    [string]$OllamaInstaller = "",
    [string]$OllamaModelsSource = "$env:USERPROFILE\.ollama\models",
    [string]$PythonInstaller = "",
    [switch]$SkipWheelDownload,
    [switch]$SkipOllamaModels
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BundleRoot = Join-Path $ProjectRoot $OutputDir
$AppDir = Join-Path $BundleRoot "app"
$WheelhouseDir = Join-Path $BundleRoot "wheelhouse"
$VendorDir = Join-Path $BundleRoot "vendor"
$VendorPythonDir = Join-Path $VendorDir "python"
$VendorOllamaDir = Join-Path $VendorDir "ollama"
$VendorOllamaModelsDir = Join-Path $VendorOllamaDir "models"

function New-CleanDirectory {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Copy-ProjectTree {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    $excludeDirs = @(
        ".git",
        ".idea",
        ".pytest_cache",
        ".pytest_work",
        ".exam_scheduler_cache",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "outputs",
        "performance_logs",
        "test_master_output"
    )
    $excludeFiles = @("*.pyc", "*.pyo", "*.log", "security_log.txt")

    robocopy $Source $Destination /E /XD $excludeDirs /XF $excludeFiles /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed while copying application files. Exit code: $LASTEXITCODE"
    }
}

New-CleanDirectory -Path $BundleRoot
New-Item -ItemType Directory -Path $AppDir, $WheelhouseDir, $VendorPythonDir, $VendorOllamaDir | Out-Null

Write-Host "Copying ExamScheduler application files..."
Copy-ProjectTree -Source $ProjectRoot -Destination $AppDir

Write-Host "Copying offline installer scripts..."
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\install_offline.ps1") -Destination (Join-Path $BundleRoot "install_offline.ps1") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\verify_offline_install.ps1") -Destination (Join-Path $BundleRoot "verify_offline_install.ps1") -Force

if (-not $SkipWheelDownload) {
    Write-Host "Downloading Python runtime wheels into wheelhouse..."
    $requirementsPath = Join-Path $ProjectRoot $RuntimeRequirements
    if (-not (Test-Path -LiteralPath $requirementsPath)) {
        throw "Runtime requirements file not found: $requirementsPath"
    }
    python -m pip download --only-binary=:all: --dest $WheelhouseDir -r $requirementsPath
}

if ($PythonInstaller) {
    if (-not (Test-Path -LiteralPath $PythonInstaller)) {
        throw "Python installer not found: $PythonInstaller"
    }
    Copy-Item -LiteralPath $PythonInstaller -Destination (Join-Path $VendorPythonDir "python-installer.exe") -Force
} else {
    Write-Warning "No Python installer was provided. The offline PC must already have Python or you must add vendor\python\python-installer.exe before delivery."
}

if ($OllamaInstaller) {
    if (-not (Test-Path -LiteralPath $OllamaInstaller)) {
        throw "Ollama installer not found: $OllamaInstaller"
    }
    Copy-Item -LiteralPath $OllamaInstaller -Destination (Join-Path $VendorOllamaDir "OllamaSetup.exe") -Force
} else {
    Write-Warning "No Ollama installer was provided. Add vendor\ollama\OllamaSetup.exe before delivery if the target PC does not already have Ollama."
}

if (-not $SkipOllamaModels) {
    if (-not (Test-Path -LiteralPath $OllamaModelsSource)) {
        throw "Ollama models folder not found: $OllamaModelsSource. Run 'ollama pull $ModelName' on this build PC first, or pass -SkipOllamaModels."
    }

    Write-Host "Copying Ollama model store. This may take a while..."
    New-Item -ItemType Directory -Path $VendorOllamaModelsDir -Force | Out-Null
    robocopy $OllamaModelsSource $VendorOllamaModelsDir /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed while copying Ollama models. Exit code: $LASTEXITCODE"
    }
}

$manifest = [ordered]@{
    name = "ExamScheduler offline bundle"
    created_utc = (Get-Date).ToUniversalTime().ToString("o")
    model_name = $ModelName
    runtime_requirements = $RuntimeRequirements
    app_dir = "app"
    wheelhouse_dir = "wheelhouse"
    ollama_models_dir = "vendor\ollama\models"
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $BundleRoot "bundle_manifest.json") -Encoding UTF8

Write-Host ""
Write-Host "Offline bundle created at: $BundleRoot"
Write-Host "Copy this folder, or zip it, and run install_offline.ps1 on the standalone PC."

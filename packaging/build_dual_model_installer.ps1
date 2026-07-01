param(
    [string]$OutputDir = "dist\ExamSchedulerInstaller",
    [string]$WheelhouseSource = "",
    [string]$PythonRuntimeSource = "",
    [string]$OllamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    [string]$OllamaModelsSource = "$env:USERPROFILE\.ollama\models",
    [string]$InnoCompiler = "",
    [switch]$SkipWheelDownload,
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputRoot = Join-Path $ProjectRoot $OutputDir
$PayloadRoot = Join-Path $OutputRoot "payload"
$AppDir = Join-Path $PayloadRoot "app"
$WheelhouseDir = Join-Path $PayloadRoot "wheelhouse"
$PythonRuntimeDir = Join-Path $PayloadRoot "runtime\python"
$ScriptsDir = Join-Path $PayloadRoot "scripts"
$VendorOllamaDir = Join-Path $PayloadRoot "vendor\ollama"
$ModelsDir = Join-Path $PayloadRoot "models"
$ManifestPath = Join-Path $OutputRoot "payload_manifest.json"

function New-CleanDirectory {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Copy-Directory {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string[]]$ExcludeDirs = @(),
        [string[]]$ExcludeFiles = @()
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $arguments = @($Source, $Destination, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    if ($ExcludeDirs.Count -gt 0) {
        $arguments += "/XD"
        $arguments += $ExcludeDirs
    }
    if ($ExcludeFiles.Count -gt 0) {
        $arguments += "/XF"
        $arguments += $ExcludeFiles
    }
    robocopy @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed copying $Source to $Destination. Exit code: $LASTEXITCODE"
    }
}

function Copy-ReleaseApplication {
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    $directories = @("src", "data", "docs")
    foreach ($directory in $directories) {
        $source = Join-Path $ProjectRoot $directory
        if (Test-Path -LiteralPath $source) {
            Copy-Directory `
                -Source $source `
                -Destination (Join-Path $AppDir $directory) `
                -ExcludeDirs @("__pycache__", ".pytest_cache", ".pytest_work", "archive") `
                -ExcludeFiles @("*.pyc", "*.pyo", "*.log")
        }
    }

    $files = @(
        "main.py",
        "gui_main.py",
        "schedule_sorter.py",
        "config.json",
        "requirements-runtime.txt",
        "README.md",
        "Courses_0_17_combined.txt"
    )
    foreach ($file in $files) {
        $source = Join-Path $ProjectRoot $file
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $AppDir $file) -Force
        }
    }
}

function Get-PythonRuntimeSource {
    if ($PythonRuntimeSource) {
        if (-not (Test-Path -LiteralPath $PythonRuntimeSource)) {
            throw "Python runtime source not found: $PythonRuntimeSource"
        }
        return (Resolve-Path $PythonRuntimeSource).Path
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python was not found on PATH. Pass -PythonRuntimeSource."
    }
    $pythonExe = & python -c "import sys; print(sys.executable)"
    return (Split-Path $pythonExe -Parent)
}

function Copy-Wheelhouse {
    if ($WheelhouseSource) {
        if (-not (Test-Path -LiteralPath $WheelhouseSource)) {
            throw "Wheelhouse source not found: $WheelhouseSource"
        }
        Copy-Directory -Source (Resolve-Path $WheelhouseSource).Path -Destination $WheelhouseDir
        return
    }

    if ($SkipWheelDownload) {
        throw "No -WheelhouseSource was provided and -SkipWheelDownload was set."
    }

    New-Item -ItemType Directory -Path $WheelhouseDir -Force | Out-Null
    & python -m pip download --only-binary=:all: --dest $WheelhouseDir -r (Join-Path $ProjectRoot "requirements-runtime.txt")
}

function Export-OllamaModel {
    param(
        [Parameter(Mandatory=$true)][string]$ModelName,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][string]$ModelKey
    )

    if ($ModelName -notmatch "^([^:]+):(.+)$") {
        throw "Model name must include a tag: $ModelName"
    }
    $repository = $Matches[1]
    $tag = $Matches[2]
    $manifest = Join-Path $OllamaModelsSource "manifests\registry.ollama.ai\library\$repository\$tag"
    if (-not (Test-Path -LiteralPath $manifest)) {
        throw "Ollama manifest not found for $ModelName`: $manifest"
    }

    $manifestDestination = Join-Path $Destination "manifests\registry.ollama.ai\library\$repository"
    New-Item -ItemType Directory -Path $manifestDestination -Force | Out-Null
    Copy-Item -LiteralPath $manifest -Destination (Join-Path $manifestDestination $tag) -Force

    $manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $digests = @()
    if ($manifestJson.config.digest) {
        $digests += $manifestJson.config.digest
    }
    foreach ($layer in $manifestJson.layers) {
        if ($layer.digest) {
            $digests += $layer.digest
        }
    }

    $blobDestination = Join-Path $Destination "blobs"
    New-Item -ItemType Directory -Path $blobDestination -Force | Out-Null
    foreach ($digest in ($digests | Select-Object -Unique)) {
        $blobName = $digest -replace ":", "-"
        $blobSource = Join-Path $OllamaModelsSource "blobs\$blobName"
        if (-not (Test-Path -LiteralPath $blobSource)) {
            throw "Ollama blob not found for $ModelName`: $blobSource"
        }
        Copy-Item -LiteralPath $blobSource -Destination (Join-Path $blobDestination $blobName) -Force
    }

    $size = (Get-ChildItem -LiteralPath $Destination -Recurse -File | Measure-Object Length -Sum).Sum
    return [ordered]@{
        key = $ModelKey
        name = $ModelName
        repository = $repository
        tag = $tag
        bytes = [int64]$size
    }
}

function Resolve-InnoCompiler {
    if ($InnoCompiler) {
        if (-not (Test-Path -LiteralPath $InnoCompiler)) {
            throw "Inno Setup compiler not found: $InnoCompiler"
        }
        return (Resolve-Path $InnoCompiler).Path
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return ""
}

New-CleanDirectory -Path $OutputRoot
New-Item -ItemType Directory -Path $PayloadRoot, $ScriptsDir, $VendorOllamaDir, $ModelsDir | Out-Null

Write-Host "Copying release application files..."
Copy-ReleaseApplication

Write-Host "Preparing Python wheelhouse..."
Copy-Wheelhouse

Write-Host "Copying bundled Python runtime..."
$pythonSource = Get-PythonRuntimeSource
Copy-Directory `
    -Source $pythonSource `
    -Destination $PythonRuntimeDir `
    -ExcludeDirs @("__pycache__", "Lib\test", "tcl\tk8.6\demos") `
    -ExcludeFiles @("*.pyc", "*.pyo")

if (-not (Test-Path -LiteralPath $OllamaExe)) {
    throw "Ollama executable not found: $OllamaExe"
}
Write-Host "Copying Ollama executable..."
Copy-Item -LiteralPath $OllamaExe -Destination (Join-Path $VendorOllamaDir "ollama.exe") -Force

Write-Host "Exporting selected Ollama models..."
$modelResults = @()
$modelResults += Export-OllamaModel `
    -ModelName "llama3.1:8b-instruct-q4_K_M" `
    -ModelKey "llama" `
    -Destination (Join-Path $ModelsDir "llama")
$modelResults += Export-OllamaModel `
    -ModelName "qwen3:4b" `
    -ModelKey "qwen" `
    -Destination (Join-Path $ModelsDir "qwen")

Write-Host "Copying installer helper scripts..."
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\install_embedded.ps1") -Destination (Join-Path $ScriptsDir "install_embedded.ps1") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\verify_offline_install.ps1") -Destination (Join-Path $ScriptsDir "verify_offline_install.ps1") -Force

$payloadSize = (Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File | Measure-Object Length -Sum).Sum
$manifest = [ordered]@{
    name = "ExamScheduler dual-model offline installer payload"
    created_utc = (Get-Date).ToUniversalTime().ToString("o")
    excluded = @("outputs", "performance_logs", "test_master_output", ".git", ".pytest_cache", ".pytest_work", "__pycache__", "src\archive")
    payload_root = $PayloadRoot
    payload_bytes = [int64]$payloadSize
    payload_gib = [math]::Round($payloadSize / 1GB, 3)
    models = $modelResults
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

Write-Host ""
Write-Host "Payload staged at: $PayloadRoot"
Write-Host ("Payload size: {0:N2} GiB" -f ($payloadSize / 1GB))
Write-Host "Manifest: $ManifestPath"

if ($SkipCompile) {
    Write-Host "Skipping installer compilation because -SkipCompile was set."
    exit 0
}

$compiler = Resolve-InnoCompiler
if (-not $compiler) {
    Write-Warning "Inno Setup compiler was not found. Install Inno Setup 6, then rerun this script without -SkipCompile."
    exit 2
}

$iss = Join-Path $ProjectRoot "packaging\ExamSchedulerDualModel.iss"
$distRoot = Join-Path $ProjectRoot "dist"
Write-Host "Compiling Inno Setup installer..."
& $compiler "/DSourceRoot=$PayloadRoot" "/DOutputRoot=$distRoot" $iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
}

Write-Host "Installer created under: $distRoot"

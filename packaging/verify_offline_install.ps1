param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\ExamScheduler",
    [string]$ModelName = "llama3.1:8b-instruct-q4_K_M",
    [switch]$RunModelSmokeTest
)

$ErrorActionPreference = "Stop"

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$AppDir = Join-Path $InstallRoot "app"
$PythonExe = Join-Path $InstallRoot ".venv\Scripts\python.exe"
$BundledOllama = Join-Path $InstallRoot "ollama\ollama.exe"
$BundledModels = Join-Path $InstallRoot "ollama\models"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python virtual environment not found: $PythonExe"
}

Write-Host "Checking Python runtime imports..."
& $PythonExe -c "import PyQt6, reportlab; print('Python runtime OK')"

Write-Host "Checking CLI entry point..."
& $PythonExe (Join-Path $AppDir "main.py") --help | Out-Null
Write-Host "CLI entry point OK"

$ollama = $null
if (Test-Path -LiteralPath $BundledOllama) {
    $ollama = @{ Source = $BundledOllama }
    $env:OLLAMA_MODELS = $BundledModels
} else {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        $ollama = @{ Source = $ollamaCommand.Source }
    } else {
        $localOllama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path -LiteralPath $localOllama) {
            $ollama = @{ Source = $localOllama }
        }
    }
}

if (-not $ollama) {
    Write-Warning "Ollama command not found. AI Copilot will fail closed until Ollama is installed."
    exit 0
}

Write-Host "Checking Ollama model list..."
$modelList = & $ollama.Source ls
if ($modelList -notmatch [regex]::Escape($ModelName)) {
    Write-Warning "Expected model was not listed by Ollama: $ModelName"
} else {
    Write-Host "Ollama model found: $ModelName"
}

if ($RunModelSmokeTest) {
    Write-Host "Running a short Ollama model smoke test..."
    & $ollama.Source run $ModelName "Return only JSON: {`"ok`": true}" --format json
}

Write-Host "Offline install verification complete."

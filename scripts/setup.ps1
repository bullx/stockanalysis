# Windows setup. From the repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
# Continue: pip and npm write warnings to stderr, and Stop would treat those as a failed setup.
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

function Stop-Setup([string]$Message) {
    Write-Host $Message
    exit 1
}

$pythonCmd = $null
$pythonArgs = @()
$versionCheck = "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 -c $versionCheck 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = "py"
        $pythonArgs = @("-3.11")
    } else {
        & py -3 -c $versionCheck 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "py"
            $pythonArgs = @("-3")
        }
    }
}
if (-not $pythonCmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c $versionCheck 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = "python"
    }
}
if (-not $pythonCmd) {
    Stop-Setup "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/ and include the py launcher."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Stop-Setup "Node.js 18 or newer is required. Install it from https://nodejs.org/"
}
$nodeVersion = (& node -v).Trim().TrimStart("v")
$nodeMajor = [int]($nodeVersion.Split(".")[0])
if ($nodeMajor -lt 18) {
    Stop-Setup "Node.js $nodeVersion is installed. This app needs 18 or newer."
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating .venv"
    if ($pythonArgs.Count -gt 0) {
        & $pythonCmd @pythonArgs -m venv (Join-Path $Root ".venv")
    } else {
        & $pythonCmd -m venv (Join-Path $Root ".venv")
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installing Python packages"
& $venvPython -m pip install -r (Join-Path $Root "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Installing frontend packages"
Push-Location (Join-Path $Root "frontend")
try {
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

$envFile = Join-Path $Root ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination $envFile
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists. Left it unchanged."
}

Write-Host ""
Write-Host "Setup finished."
Write-Host "Start the app with:  powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1"
Write-Host "The default is Ollama and llama3.1:8b. To click through the UI with no model, set LLM_PROVIDER=mock and LLM_MODEL=mock in .env."

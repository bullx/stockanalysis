# One process. Builds the UI if Node is available, then the API serves it.
#   powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
# After the first build, Node is not required to open the app.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

$dist = Join-Path $Root "frontend\dist\index.html"
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Write-Host "Building the UI..."
    Push-Location (Join-Path $Root "frontend")
    npm run build
    Pop-Location
} elseif (-not (Test-Path -LiteralPath $dist)) {
    Write-Host "Node is not installed and frontend\dist is missing. Install Node 18+ once, run this script again, then later starts do not need Node."
    exit 1
}

Write-Host "Open http://127.0.0.1:8000"
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

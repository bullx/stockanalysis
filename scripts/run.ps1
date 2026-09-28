# Windows run. Starts the API and the UI in two windows.
#   powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

function Stop-Run([string]$Message) {
    Write-Host $Message
    exit 1
}

function Get-DotEnvValue([string]$Name) {
    $path = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $path)) { return "" }
    foreach ($raw in Get-Content -LiteralPath $path) {
        $line = $raw.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
        if ($line.StartsWith("export ")) { $line = $line.Substring(7).Trim() }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        if ($key -ne $Name) { continue }
        $val = $line.Substring($eq + 1).Trim()
        if ($val.Length -ge 2) {
            $quote = $val.Substring(0, 1)
            if (($quote -eq '"' -or $quote -eq "'") -and $val.EndsWith($quote)) {
                $val = $val.Substring(1, $val.Length - 2)
            }
        }
        return $val
    }
    return ""
}

function Test-PortOpen([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $wait.AsyncWaitHandle.WaitOne(400)) { return $false }
        $client.EndConnect($wait)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath (Join-Path $Root "frontend\node_modules"))) {
    Stop-Run "Run setup first:  powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1"
}

if ((Test-PortOpen 8000) -or (Test-PortOpen 5173)) {
    Stop-Run "Port 8000 or 5173 is already in use. Stop that process, or open http://localhost:5173 if this app is already running."
}

$provider = Get-DotEnvValue "LLM_PROVIDER"
if (-not $provider) { $provider = "ollama" }
$model = Get-DotEnvValue "LLM_MODEL"
if (-not $model) { $model = "llama3.1:8b" }
$apiKey = Get-DotEnvValue "LLM_API_KEY"
$local = @("ollama", "lmstudio", "llamacpp", "jan", "llamafile", "mock")

if ($local -notcontains $provider.ToLower()) {
    if (-not $apiKey) {
        Stop-Run "LLM_PROVIDER=$provider needs LLM_API_KEY in .env. Save the file, then run this script again."
    }
}

if ($provider.ToLower() -eq "ollama") {
    # A -c string loses its quotes when PowerShell launches python.exe. A file does not.
    $probePath = Join-Path $env:TEMP "aurelia-ollama-probe.py"
    $probe = @'
import sys, urllib.request
model = sys.argv[1]
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as resp:
        body = resp.read().decode()
except Exception:
    raise SystemExit(2)
if model not in body:
    raise SystemExit(3)
raise SystemExit(0)
'@
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($probePath, $probe.Replace("`r`n", "`n"), $utf8)
    & $venvPython $probePath $model
    if ($LASTEXITCODE -eq 2) {
        Stop-Run "Ollama is not answering on port 11434. Install it from https://ollama.com, run 'ollama pull $model', and start the Ollama app. If that app is already open, do not also run 'ollama serve'."
    }
    if ($LASTEXITCODE -eq 3) {
        Stop-Run "Ollama is up, and $model is not pulled. Run:  ollama pull $model"
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Escape-PsSingle([string]$Value) {
    return $Value.Replace("'", "''")
}

$rootEsc = Escape-PsSingle $Root
$pythonEsc = Escape-PsSingle $venvPython
$apiCommand = "Set-Location -LiteralPath '$rootEsc'; & '$pythonEsc' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $apiCommand) | Out-Null

$frontEsc = Escape-PsSingle (Join-Path $Root "frontend")
$uiCommand = "Set-Location -LiteralPath '$frontEsc'; npm run dev"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $uiCommand) | Out-Null

Write-Host "API  http://127.0.0.1:8000/api/health"
Write-Host "UI   http://localhost:5173"
Write-Host "Close those two windows to stop. After you edit .env, close them and run this script again."

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

Set-Location $PSScriptRoot

$exePath = Join-Path $PSScriptRoot "dist\CopilotBridge.exe"
if (Test-Path $exePath) {
    Start-Process -FilePath $exePath
    exit 0
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Create it first with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

& ".\.venv\Scripts\python.exe" ".\main.py"

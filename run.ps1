$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Create it first with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

& ".\.venv\Scripts\python.exe" ".\main.py"

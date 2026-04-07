$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) {
        throw "Failed to create virtual environment."
    }
}

& $python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build dependencies."
}

$specPath = Join-Path $PSScriptRoot "CopilotCLI-Feishu.spec"
if (Test-Path $specPath) {
    Remove-Item $specPath -Force
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name "CopilotCLI-Feishu" `
    --collect-submodules lark_oapi `
    --collect-submodules requests `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Write-Host "Build complete: dist\CopilotCLI-Feishu.exe" -ForegroundColor Green

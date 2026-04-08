param(
    [string]$IconPath = ""
)

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

$generatedIcon = Join-Path $PSScriptRoot "build\app-icon.ico"
$resolvedIconPath = $IconPath
if (-not $resolvedIconPath) {
    $iconCandidates = @(
        (Join-Path $PSScriptRoot "favicon.ico"),
        (Join-Path $PSScriptRoot "favicon (1).ico"),
        $generatedIcon
    )
    foreach ($candidate in $iconCandidates) {
        if (Test-Path $candidate) {
            $resolvedIconPath = $candidate
            break
        }
    }
}

if (-not $resolvedIconPath) {
    $resolvedIconPath = $generatedIcon
}

if (-not (Test-Path (Split-Path $resolvedIconPath -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $resolvedIconPath -Parent) -Force | Out-Null
}

if (-not (Test-Path $resolvedIconPath)) {
    $iconScript = @'
from pathlib import Path
import sys

from PIL import Image, ImageDraw

target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)

size = 256
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((18, 18, size - 18, size - 18), radius=56, fill=(17, 24, 39, 255))
draw.rounded_rectangle((44, 44, size - 44, size - 44), radius=44, fill=(44, 199, 183, 255))
draw.rounded_rectangle((74, 74, size - 74, size - 74), radius=32, fill=(26, 86, 219, 255))
draw.text((84, 60), "C", fill=(255, 255, 255, 255))
image.save(target, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
'@
    & $python -c $iconScript $resolvedIconPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $resolvedIconPath)) {
        throw "Failed to generate application icon."
    }
}

$specPath = Join-Path $PSScriptRoot "CopilotCLI-Feishu.spec"
if (Test-Path $specPath) {
    Remove-Item $specPath -Force
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "CopilotCLI-Feishu" `
    --icon $resolvedIconPath `
    --collect-submodules lark_oapi `
    --collect-submodules requests `
    --collect-submodules pystray `
    --collect-submodules PIL `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Write-Host "Build complete: dist\CopilotCLI-Feishu.exe" -ForegroundColor Green

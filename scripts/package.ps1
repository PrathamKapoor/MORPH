# MORPH 2.0 PyInstaller Packaging Script for Windows
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
if (-not $root) { $root = (Get-Location).Path }
Set-Location -LiteralPath $root

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Virtual environment Python not found at $py"
    exit 1
}

$taskModel = "models\face_landmarker.task"
if (-not (Test-Path $taskModel)) {
    Write-Error "Model asset missing at $taskModel. Run doctor.ps1 first."
    exit 1
}

Write-Host "Packaging MORPH 2.0 with PyInstaller (One-Folder Mode)..." -ForegroundColor Cyan

$distDir = "$root\dist"
$buildDir = "$root\build"

& $py -m PyInstaller `
    --noconfirm `
    --onedir `
    --windowed `
    --name morph `
    --add-data "models;models" `
    --paths "src" `
    --distpath $distDir `
    --workpath $buildDir `
    src\morph\__main__.py

$exePath = "$distDir\morph\morph.exe"
if (Test-Path $exePath) {
    Write-Host "`nPackage build SUCCESSFUL!" -ForegroundColor Green
    Write-Host "Executable location: $exePath" -ForegroundColor Green
    Write-Host "Asset bundled: $distDir\morph\_internal\models\face_landmarker.task" -ForegroundColor Green
    exit 0
} else {
    Write-Error "Build failed: $exePath not found!"
    exit 1
}

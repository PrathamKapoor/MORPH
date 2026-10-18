# MORPH 2.0 Quickstart Run Script
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
if (-not $root) { $root = (Get-Location).Path }
Set-Location -LiteralPath $root

$env:PIP_CACHE_DIR = "$root\.cache\pip"
$env:TEMP = "$root\.tmp"
$env:TMP = "$root\.tmp"

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Virtual environment Python not found! Run doctor.ps1 first."
    exit 1
}

Write-Host "Launching MORPH 2.0..." -ForegroundColor Cyan
& $py -m morph @args

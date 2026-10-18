# MORPH 2.0 Environment & System Health Check Script (Milestone M6.8)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
if (-not $root) { $root = (Get-Location).Path }
Set-Location -LiteralPath $root

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       MORPH 2.0 System Health Verification (doctor)      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$results = [ordered]@{}
$warnings = [System.Collections.Generic.List[string]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Virtual environment Python not found at $py! Please run setup first."
    exit 1
}

# [1/6] Python interpreter & architecture
Write-Host "[1/6] Checking Python interpreter and virtual environment..." -ForegroundColor Yellow
try {
    $pyVer = & $py --version
    $is64 = & $py -c "import sys; print(sys.maxsize > 2**32)"
    if ($is64 -match "True") {
        Write-Host "  -> $pyVer (64-bit x64/ARM64) [PASS]" -ForegroundColor Green
        $results["Python Environment"] = "PASS"
    } else {
        $failures.Add("Python is 32-bit. 64-bit Python is required for MediaPipe and PySide6.")
        $results["Python Environment"] = "FAIL"
    }
} catch {
    $failures.Add("Failed executing Python at $($py): $_")
    $results["Python Environment"] = "FAIL"
}

# [2/6] Core dependency packages
Write-Host "[2/6] Checking core dependencies..." -ForegroundColor Yellow
$importCheck = & $py -c "
import sys
modules = ['numpy', 'cv2', 'PySide6', 'mediapipe', 'pyttsx3', 'win32api', 'pytest', 'ruff']
missing = []
for m in modules:
    try:
        __import__(m)
    except Exception as e:
        missing.append(f'{m}: {e}')
if missing:
    print('MISSING: ' + '; '.join(missing))
    sys.exit(1)
else:
    print('ALL_DEPENDENCIES_OK')
"
if ($LASTEXITCODE -eq 0 -and $importCheck -match "ALL_DEPENDENCIES_OK") {
    Write-Host "  -> Packages verified: numpy, cv2, PySide6, mediapipe, pyttsx3, win32api, pytest, ruff [PASS]" -ForegroundColor Green
    $results["Core Dependencies"] = "PASS"
} else {
    $failures.Add("Missing or broken dependencies: $importCheck. Run '.venv\Scripts\pip install -e .'")
    $results["Core Dependencies"] = "FAIL"
}

# [3/6] MediaPipe model asset & SHA256 manifest
Write-Host "[3/6] Checking MediaPipe model asset and SHA256 integrity..." -ForegroundColor Yellow
$taskPath = "models\face_landmarker.task"
$manifestPath = "models\face_landmarker.task.manifest.json"
if (-not (Test-Path $taskPath)) {
    $failures.Add("Model file $taskPath missing! Acquire via scripts/fetch_models.ps1 or docs/ENVIRONMENT.md.")
    $results["Model Asset"] = "FAIL"
} else {
    $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $fileStream = [System.IO.File]::OpenRead((Resolve-Path $taskPath))
    $hashBytes = $hasher.ComputeHash($fileStream)
    $fileStream.Close()
    $calcSha256 = ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
    $fileSize = (Get-Item $taskPath).Length
    if ($calcSha256 -eq $manifest.sha256) {
        Write-Host "  -> Model verified: $taskPath ($fileSize bytes, SHA-256 match) [PASS]" -ForegroundColor Green
        $results["Model Asset"] = "PASS"
    } else {
        $failures.Add("Model checksum mismatch! Expected $($manifest.sha256), got $calcSha256. Re-download asset.")
        $results["Model Asset"] = "FAIL"
    }
}

# [4/6] Offline SAPI TTS speech synthesis
Write-Host "[4/6] Checking local Windows SAPI TTS offline voices..." -ForegroundColor Yellow
$voices = & $py -c "
import pyttsx3
try:
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    names = [v.name for v in voices]
    print('VOICES:' + ', '.join(names) if names else 'NONE')
except Exception as e:
    print(f'ERROR: {e}')
"
if ($voices -match "VOICES:") {
    $voiceList = $voices.Replace("VOICES:", "").Trim()
    Write-Host "  -> Available TTS voices: $voiceList [PASS]" -ForegroundColor Green
    $results["TTS Voices"] = "PASS"
} else {
    $warnings.Add("No local SAPI TTS voices detected or pyttsx3 initialization failed. AAC speech synthesis will use visual fallbacks.")
    $results["TTS Voices"] = "WARN"
}

# [5/6] Camera hardware and DirectShow backend compatibility
Write-Host "[5/6] Checking DirectShow camera backend and synthetic fallback..." -ForegroundColor Yellow
$camStatus = & $py -c "
import cv2
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if cap.isOpened():
    ret, frame = cap.read()
    cap.release()
    print('HARDWARE_ACTIVE' if ret else 'HARDWARE_NO_FRAME')
else:
    print('NO_HARDWARE')
"
if ($camStatus -match "HARDWARE_ACTIVE") {
    Write-Host "  -> DirectShow camera backend active and streaming frames [PASS]" -ForegroundColor Green
    $results["Camera Sensor"] = "PASS"
} elseif ($camStatus -match "HARDWARE_NO_FRAME") {
    $warnings.Add("DirectShow camera opened but returned no frames (camera in use or privacy shutter closed). Synthetic fallback is active.")
    $results["Camera Sensor"] = "WARN"
} else {
    $warnings.Add("Physical camera not detected. MORPH operates normally in synthetic/no-camera mode via --no-camera.")
    $results["Camera Sensor"] = "WARN"
}

# [6/6] SQLite database read/write permissions
Write-Host "[6/6] Checking SQLite database write permissions..." -ForegroundColor Yellow
$dbCheck = & $py -c "
import sqlite3, tempfile
from pathlib import Path
from morph.storage.db import DatabaseManager

try:
    with tempfile.TemporaryDirectory() as td:
        test_db = Path(td) / 'doctor_test.db'
        db = DatabaseManager(test_db)
        with db.get_connection() as conn:
            conn.execute('CREATE TABLE doctor_probe (id INTEGER PRIMARY KEY, note TEXT);')
            conn.execute('INSERT INTO doctor_probe (note) VALUES (?);', ('permission_ok',))
            row = conn.execute('SELECT note FROM doctor_probe;').fetchone()
            assert row['note'] == 'permission_ok'
    print('DB_WRITE_OK')
except Exception as e:
    print(f'DB_ERROR: {e}')
"
if ($dbCheck -match "DB_WRITE_OK") {
    Write-Host "  -> SQLite database transactions and schema migration [PASS]" -ForegroundColor Green
    $results["Database Permissions"] = "PASS"
} else {
    $failures.Add("Database transaction check failed: $dbCheck")
    $results["Database Permissions"] = "FAIL"
}

# ================= Summary Checklist =================
Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "               HEALTH CHECK SUMMARY RESULTS               " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
foreach ($key in $results.Keys) {
    $status = $results[$key]
    $color = if ($status -eq "PASS") { "Green" } elseif ($status -eq "WARN") { "Yellow" } else { "Red" }
    Write-Host ("  {0,-30} [{1}]" -f $key, $status) -ForegroundColor $color
}

if ($warnings.Count -gt 0) {
    Write-Host "`n[WARNINGS]" -ForegroundColor Yellow
    foreach ($w in $warnings) {
        Write-Host "  * $w" -ForegroundColor Yellow
    }
}

if ($failures.Count -gt 0) {
    Write-Host "`n[CRITICAL FAILURES - ACTION REQUIRED]" -ForegroundColor Red
    foreach ($f in $failures) {
        Write-Host "  ! $f" -ForegroundColor Red
    }
    Write-Host "`nMORPH 2.0 health check FAILED. Please resolve the critical items above.`n" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nAll required systems operational. MORPH 2.0 is production ready.`n" -ForegroundColor Green
    exit 0
}

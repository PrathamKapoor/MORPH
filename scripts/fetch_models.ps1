# MORPH 2.0 MediaPipe Model Asset Downloader & Checksum Verifier
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
if (-not $root) { $root = (Get-Location).Path }
Set-Location -LiteralPath $root

$modelsDir = Join-Path $root "models"
$manifestPath = Join-Path $modelsDir "face_landmarker.task.manifest.json"
$targetPath = Join-Path $modelsDir "face_landmarker.task"

if (-not (Test-Path $manifestPath)) {
    Write-Error "Model manifest missing at $manifestPath"
    exit 1
}

$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
$expectedSha256 = $manifest.sha256
$sourceUrl = $manifest.source_url

function Test-ModelChecksum {
    param([string]$FilePath, [string]$ExpectedHash)
    if (-not (Test-Path $FilePath)) { return $false }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead((Resolve-Path $FilePath))
    $hashBytes = $hasher.ComputeHash($stream)
    $stream.Close()
    $actualHash = ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
    return ($actualHash -eq $ExpectedHash)
}

Write-Host "Verifying MediaPipe Face Landmarker model asset..." -ForegroundColor Cyan

if (Test-ModelChecksum -FilePath $targetPath -ExpectedHash $expectedSha256) {
    $fileSize = (Get-Item $targetPath).Length
    Write-Host "Model asset already present and verified ($fileSize bytes, SHA-256 match)." -ForegroundColor Green
    exit 0
}

Write-Host "Downloading model asset from $sourceUrl..." -ForegroundColor Yellow
if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
}

$tempDownload = "$targetPath.tmp"
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($sourceUrl, $tempDownload)
    $webClient.Dispose()

    if (Test-ModelChecksum -FilePath $tempDownload -ExpectedHash $expectedSha256) {
        Move-Item -Force -Path $tempDownload -Destination $targetPath
        $fileSize = (Get-Item $targetPath).Length
        Write-Host "Model downloaded and verified successfully ($fileSize bytes)." -ForegroundColor Green
        exit 0
    } else {
        Remove-Item -Force -Path $tempDownload -ErrorAction SilentlyContinue
        Write-Error "Downloaded model failed SHA-256 checksum verification!"
        exit 1
    }
} catch {
    Remove-Item -Force -Path $tempDownload -ErrorAction SilentlyContinue
    Write-Error "Failed to download model asset: $_"
    exit 1
}

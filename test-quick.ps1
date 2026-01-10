# Portfolio Manager - Quick Test Script
# Fast validation that services start correctly

$ErrorActionPreference = "Stop"

# Change to script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Portfolio Manager - Quick Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check prerequisites
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow
try {
    python --version | Out-Null
    node --version | Out-Null
    npm --version | Out-Null
    Write-Host "  [OK] All prerequisites found" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Missing prerequisites" -ForegroundColor Red
    exit 1
}

# Check dependencies
Write-Host "[2/6] Checking dependencies..." -ForegroundColor Yellow
if ((Test-Path "backend\venv") -and (Test-Path "frontend\node_modules")) {
    Write-Host "  [OK] Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Dependencies not installed" -ForegroundColor Red
    exit 1
}

# Stop any running services
Write-Host "[3/6] Cleaning up existing services..." -ForegroundColor Yellow
& "$ScriptDir\stop.ps1" | Out-Null
Start-Sleep -Seconds 1
Write-Host "  [OK] Cleanup complete" -ForegroundColor Green

# Start backend
Write-Host "[4/6] Starting backend..." -ForegroundColor Yellow
$backendPath = Join-Path $PWD "backend"
$backendProcess = Start-Process -FilePath "$backendPath\venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $backendPath `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

$backendReady = $false
for ($i = 0; $i -lt 15; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($backendReady) {
    Write-Host "  [OK] Backend running on port 8000" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Backend failed to start" -ForegroundColor Red
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# Start frontend
Write-Host "[5/6] Starting frontend..." -ForegroundColor Yellow
$frontendPath = Join-Path $PWD "frontend"
$frontendProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-WindowStyle", "Hidden", "-Command", "cd '$frontendPath'; npm run dev" `
    -WorkingDirectory $frontendPath `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 5

$frontendReady = $false
for ($i = 0; $i -lt 20; $i++) {
    $connection = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($connection) {
        $frontendReady = $true
        break
    }
    Start-Sleep -Seconds 1
}

if ($frontendReady) {
    Write-Host "  [OK] Frontend running on port 5173" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Frontend failed to start" -ForegroundColor Red
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# Test API endpoints
Write-Host "[6/6] Testing API endpoints..." -ForegroundColor Yellow
$apiTests = @(
    @{ Name = "Health"; Url = "http://localhost:8000/health" },
    @{ Name = "Transactions"; Url = "http://localhost:8000/api/transactions/" },
    @{ Name = "Portfolio"; Url = "http://localhost:8000/api/portfolio/summary" }
)

$allPassed = $true
foreach ($test in $apiTests) {
    try {
        $response = Invoke-WebRequest -Uri $test.Url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ne 200) {
            $allPassed = $false
        }
    } catch {
        $allPassed = $false
    }
}

if ($allPassed) {
    Write-Host "  [OK] All API endpoints responding" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Some API endpoints failed" -ForegroundColor Yellow
}

# Cleanup
Write-Host "`nCleaning up..." -ForegroundColor Gray
Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue

# Clean up any remaining processes
Start-Sleep -Seconds 1
$backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($backend) {
    Stop-Process -Id $backend.OwningProcess -Force -ErrorAction SilentlyContinue
}
$frontend = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($frontend) {
    Stop-Process -Id $frontend.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "All tests passed!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

exit 0

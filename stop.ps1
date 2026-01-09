# Portfolio Manager - Stop Script
# Stops all Portfolio Manager services

Write-Host "`nStopping Portfolio Manager services...`n" -ForegroundColor Cyan

$stopped = $false

# Find and stop processes on port 8000 (backend)
Write-Host "Checking for backend processes..." -ForegroundColor Yellow
$backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($backend) {
    $backendPID = $backend.OwningProcess
    Write-Host "  --> Stopping backend (PID: $backendPID)..." -ForegroundColor Gray
    Stop-Process -Id $backendPID -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Backend stopped" -ForegroundColor Green
    $stopped = $true
} else {
    Write-Host "  No backend process found" -ForegroundColor Gray
}

# Find and stop processes on port 5173 (frontend)
Write-Host "`nChecking for frontend processes..." -ForegroundColor Yellow
$frontend = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($frontend) {
    $frontendPID = $frontend.OwningProcess
    Write-Host "  --> Stopping frontend (PID: $frontendPID)..." -ForegroundColor Gray
    Stop-Process -Id $frontendPID -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Frontend stopped" -ForegroundColor Green
    $stopped = $true
} else {
    Write-Host "  No frontend process found" -ForegroundColor Gray
}

if ($stopped) {
    Write-Host "`n[OK] All Portfolio Manager services stopped`n" -ForegroundColor Green
} else {
    Write-Host "`nNo running services found`n" -ForegroundColor Yellow
}

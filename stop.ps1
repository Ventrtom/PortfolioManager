# Portfolio Manager - Stop Script
# Stops all Portfolio Manager services

Write-Host "`nStopping Portfolio Manager services...`n" -ForegroundColor Cyan

$stopped = $false

# Kill all python processes from backend virtual environment
Write-Host "Checking for backend processes..." -ForegroundColor Yellow
$backendPythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*PortfolioManager\backend\venv*"
}

if ($backendPythonProcesses) {
    foreach ($proc in $backendPythonProcesses) {
        Write-Host "  --> Stopping backend (PID: $($proc.Id))..." -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
    Write-Host "  [OK] Backend processes stopped" -ForegroundColor Green
} else {
    Write-Host "  No backend process found" -ForegroundColor Gray
}

# Also check port 8000 directly
$backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($backend) {
    $backendPID = $backend.OwningProcess
    $processExists = Get-Process -Id $backendPID -ErrorAction SilentlyContinue
    if ($processExists) {
        Write-Host "  --> Also stopping process on port 8000 (PID: $backendPID)..." -ForegroundColor Gray
        Stop-Process -Id $backendPID -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
}

# Find and stop processes on port 5173 (frontend)
Write-Host "`nChecking for frontend processes..." -ForegroundColor Yellow
$frontend = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($frontend) {
    $frontendPID = $frontend.OwningProcess
    $processExists = Get-Process -Id $frontendPID -ErrorAction SilentlyContinue
    if ($processExists) {
        Write-Host "  --> Stopping frontend (PID: $frontendPID)..." -ForegroundColor Gray
        Stop-Process -Id $frontendPID -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] Frontend stopped" -ForegroundColor Green
        $stopped = $true
    } else {
        Write-Host "  Port 5173 has stale connection, will clear shortly" -ForegroundColor Gray
    }
} else {
    Write-Host "  No frontend process found" -ForegroundColor Gray
}

# Wait for ports to be released (max 5 seconds)
if ($stopped) {
    Write-Host "`nWaiting for ports to be released..." -ForegroundColor Yellow
    for ($i = 1; $i -le 5; $i++) {
        Start-Sleep -Seconds 1
        $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
        $port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue

        if (-not $port8000 -and -not $port5173) {
            Write-Host "  [OK] All ports released" -ForegroundColor Green
            break
        }
    }
}

if ($stopped) {
    Write-Host "`n[OK] All Portfolio Manager services stopped`n" -ForegroundColor Green
} else {
    Write-Host "`nNo running services found`n" -ForegroundColor Yellow
}

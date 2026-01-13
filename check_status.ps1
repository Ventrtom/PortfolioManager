Write-Host "`nChecking system status...`n" -ForegroundColor Cyan

# Check port 8000
Write-Host "Port 8000:" -ForegroundColor Yellow
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000) {
    $pid = $port8000.OwningProcess
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  [ACTIVE] Used by PID $pid - $($proc.ProcessName)" -ForegroundColor Red
        Write-Host "  Path: $($proc.Path)" -ForegroundColor Gray
    } else {
        Write-Host "  [STALE] Connection exists for non-existent PID $pid" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [FREE] Port is available" -ForegroundColor Green
}

# Check port 5173
Write-Host "`nPort 5173:" -ForegroundColor Yellow
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173) {
    $pid = $port5173.OwningProcess
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  [ACTIVE] Used by PID $pid - $($proc.ProcessName)" -ForegroundColor Red
    } else {
        Write-Host "  [STALE] Connection exists for non-existent PID $pid" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [FREE] Port is available" -ForegroundColor Green
}

# Check for backend python processes
Write-Host "`nBackend Python processes:" -ForegroundColor Yellow
$backendProcs = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*PortfolioManager\backend\venv*"
}
if ($backendProcs) {
    foreach ($proc in $backendProcs) {
        Write-Host "  [RUNNING] PID $($proc.Id)" -ForegroundColor Red
    }
} else {
    Write-Host "  [NONE] No backend processes running" -ForegroundColor Green
}

Write-Host ""

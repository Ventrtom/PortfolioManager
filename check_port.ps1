Write-Host "Checking port 8000..." -ForegroundColor Cyan

for ($i = 1; $i -le 10; $i++) {
    $conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

    if (-not $conn) {
        Write-Host "[OK] Port 8000 is now free!" -ForegroundColor Green
        exit 0
    }

    $pid = $conn.OwningProcess
    $state = $conn.State
    $processExists = Get-Process -Id $pid -ErrorAction SilentlyContinue

    if ($processExists) {
        Write-Host "Attempt $i/10: Port used by active process PID $pid (State: $state)" -ForegroundColor Yellow
    } else {
        Write-Host "Attempt $i/10: Port held by non-existent PID $pid (stale connection)" -ForegroundColor Red
    }

    Start-Sleep -Seconds 1
}

Write-Host "[WARNING] Port 8000 still not free after 10 seconds" -ForegroundColor Yellow
Write-Host "Connection details:" -ForegroundColor Gray
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Format-List

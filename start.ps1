# Portfolio Manager - Startup Script
# Handles both first-time setup and subsequent launches
#
# Features:
# - Automatic dependency installation (first-time setup)
# - Version checking for Python (3.8+) and Node.js (16+)
# - Port conflict detection and cleanup
# - Process monitoring during startup
# - Visible consoles by default (both backend and frontend)
# - Simultaneous logging to startup.log files
# - Graceful shutdown on Ctrl+C
# - Health check verification before reporting success
#
# Usage:
#   .\start.ps1                  # Start with browser and visible consoles
#   .\start.ps1 -SkipBrowser     # Start without opening browser
#   .\start.ps1 -Quiet           # Hide backend/frontend consoles (log to files only)

param(
    [switch]$SkipBrowser,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

# Change to script directory (project root)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Color functions for output
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Progress { param($msg) Write-Host "  --> $msg" -ForegroundColor Yellow }
function Write-ErrorMsg { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Global variables for process management
$script:BackendProcess = $null
$script:FrontendProcess = $null

# Cleanup function
function Stop-Services {
    Write-Info "Shutting down services..."

    if ($script:BackendProcess) {
        Write-Progress "Stopping backend..."
        Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }

    if ($script:FrontendProcess) {
        Write-Progress "Stopping frontend..."
        Stop-Process -Id $script:FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }

    # Kill any remaining uvicorn or node processes on our ports
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" } | ForEach-Object {
        try {
            $connections = Get-NetTCPConnection -OwningProcess $_.Id -ErrorAction SilentlyContinue
            if ($connections | Where-Object { $_.LocalPort -eq 8000 -or $_.LocalPort -eq 5173 }) {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }

    Write-Success "All services stopped"
    Write-Host "`nThank you for using Portfolio Manager!" -ForegroundColor Cyan
}

# Register cleanup on exit
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-Services }

# Trap Ctrl+C
[Console]::TreatControlCAsInput = $false
$null = Register-EngineEvent -SourceIdentifier ConsoleCancel -Action { Stop-Services; exit }

# Banner
Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "Portfolio Manager - Startup Script" -ForegroundColor Magenta
Write-Host "========================================`n" -ForegroundColor Magenta

# Check prerequisites
Write-Info "Checking prerequisites..."

# Check Python
try {
    $pythonVersion = (python --version 2>&1) -replace "Python ", ""
    $pythonMajor = [int]($pythonVersion.Split('.')[0])
    $pythonMinor = [int]($pythonVersion.Split('.')[1])

    if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 8)) {
        Write-ErrorMsg "Python $pythonVersion is too old! Minimum required: Python 3.8"
        Write-Host "Please upgrade Python from https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
    Write-Success "Python $pythonVersion found"
} catch {
    Write-ErrorMsg "Python not found or invalid!"
    Write-Host "Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Node.js
try {
    $nodeVersion = (node --version) -replace "v", ""
    $nodeMajor = [int]($nodeVersion.Split('.')[0])

    if ($nodeMajor -lt 16) {
        Write-ErrorMsg "Node.js $nodeVersion is too old! Minimum required: Node.js 16+"
        Write-Host "Please upgrade Node.js from https://nodejs.org/" -ForegroundColor Yellow
        exit 1
    }
    Write-Success "Node.js $nodeVersion found"
} catch {
    Write-ErrorMsg "Node.js not found or invalid!"
    Write-Host "Please install Node.js 16+ from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Check npm
try {
    $npmVersion = npm --version
    Write-Success "npm $npmVersion found"
} catch {
    Write-ErrorMsg "npm not found!"
    Write-Host "Please install npm (usually comes with Node.js)" -ForegroundColor Yellow
    exit 1
}

# Check for first-time setup
$firstTime = $false
if (-not (Test-Path "backend\venv") -or -not (Test-Path "frontend\node_modules")) {
    $firstTime = $true
    Write-Host "`n[INFO] First-time setup detected`n" -ForegroundColor Cyan
}

# Backend setup
if (-not (Test-Path "backend\venv")) {
    Write-Info "Setting up backend..."
    Write-Progress "Creating virtual environment..."

    try {
        Set-Location backend
        python -m venv venv
        Write-Success "Virtual environment created"

        Write-Progress "Installing Python dependencies..."
        & ".\venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
        & ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet
        Write-Success "Backend setup complete"
        Set-Location ..
    } catch {
        Set-Location ..
        Write-ErrorMsg "Failed to setup backend: $_"
        exit 1
    }
} else {
    if ($firstTime) {
        Write-Info "Backend dependencies already installed"
    }
}

# Frontend setup
if (-not (Test-Path "frontend\node_modules")) {
    Write-Info "Setting up frontend..."
    Write-Progress "Installing Node.js dependencies..."

    try {
        Set-Location frontend
        npm install --silent 2>$null
        Write-Success "Frontend setup complete"
        Set-Location ..
    } catch {
        Set-Location ..
        Write-ErrorMsg "Failed to setup frontend: $_"
        exit 1
    }
} else {
    if ($firstTime) {
        Write-Info "Frontend dependencies already installed"
    }
}

# Check ports
Write-Info "Starting services..."

# First, clean up any stale backend processes
$backendPythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*PortfolioManager\backend\venv*"
}
if ($backendPythonProcesses) {
    Write-Progress "Cleaning up existing backend processes..."
    foreach ($proc in $backendPythonProcesses) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# Check if port 8000 is in use by an active process
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000InUse) {
    $port8000PID = $port8000InUse.OwningProcess
    $processExists = Get-Process -Id $port8000PID -ErrorAction SilentlyContinue

    if ($processExists) {
        Write-ErrorMsg "Port 8000 is already in use by process $port8000PID!"
        Write-Host "Process: $($processExists.ProcessName) - $($processExists.Path)" -ForegroundColor Yellow
        Write-Host "Run the stop script first: .\stop.ps1" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Progress "Port 8000 has stale connection, waiting for it to clear..."
        Start-Sleep -Seconds 3
        $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
        if ($port8000InUse) {
            Write-ErrorMsg "Port 8000 still not available (stale connection)"
            Write-Host "This is a Windows TCP/IP issue. Try waiting 30 seconds or run: netsh int ip reset" -ForegroundColor Yellow
            exit 1
        }
    }
}

# Check if port 5173 is in use
$port5173InUse = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173InUse) {
    $port5173PID = $port5173InUse.OwningProcess
    $processExists = Get-Process -Id $port5173PID -ErrorAction SilentlyContinue

    if ($processExists) {
        Write-ErrorMsg "Port 5173 is already in use by process $port5173PID!"
        Write-Host "Process: $($processExists.ProcessName)" -ForegroundColor Yellow
        Write-Host "Run the stop script first: .\stop.ps1" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Progress "Port 5173 has stale connection, waiting for it to clear..."
        Start-Sleep -Seconds 3
        $port5173InUse = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
        if ($port5173InUse) {
            Write-ErrorMsg "Port 5173 still not available"
            exit 1
        }
    }
}

# Start backend
Write-Progress "Starting backend API..."
try {
    $backendPath = Join-Path $PWD "backend"
    $logFile = Join-Path $backendPath "startup.log"
    $errorLogFile = Join-Path $backendPath "startup_errors.log"

    # Start backend with visible console by default, or quiet mode with logs only
    if ($Quiet) {
        # Quiet mode: redirect output to log files only
        $script:BackendProcess = Start-Process -FilePath "$backendPath\venv\Scripts\python.exe" `
            -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
            -WorkingDirectory $backendPath `
            -PassThru `
            -WindowStyle Minimized `
            -RedirectStandardError $errorLogFile `
            -RedirectStandardOutput $logFile
    } else {
        # Default: Show console and also log to file using Tee-Object
        # Set ErrorActionPreference to SilentlyContinue to avoid PowerShell formatting stderr as errors
        $backendCmd = "`$ErrorActionPreference='SilentlyContinue'; cd '$backendPath'; .\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | Tee-Object -FilePath 'startup.log'"
        $script:BackendProcess = Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-NoExit", "-Command", $backendCmd `
            -WorkingDirectory $backendPath `
            -PassThru `
            -WindowStyle Normal
    }

    # Give the process a moment to start
    Start-Sleep -Seconds 2

    # Check if process is still alive
    if (-not (Get-Process -Id $script:BackendProcess.Id -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "Backend process crashed immediately after startup"

        if (Test-Path $errorLogFile) {
            $errorContent = Get-Content $errorLogFile -Raw -ErrorAction SilentlyContinue
            if ($errorContent -and $errorContent.Trim()) {
                Write-Host "`nErrors from startup_errors.log:" -ForegroundColor Yellow
                Get-Content $errorLogFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
        }

        if (Test-Path $logFile) {
            $logContent = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
            if ($logContent -and $logContent.Trim()) {
                Write-Host "`nOutput from startup.log:" -ForegroundColor Yellow
                Get-Content $logFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
        }

        Stop-Services
        exit 1
    }

    # Wait for backend to be ready
    $maxAttempts = 30
    $attempt = 0
    $backendReady = $false

    while ($attempt -lt $maxAttempts) {
        # Check if process is still alive
        if (-not (Get-Process -Id $script:BackendProcess.Id -ErrorAction SilentlyContinue)) {
            Write-ErrorMsg "Backend process died during startup (attempt $attempt)"

            if (Test-Path $errorLogFile) {
                $errorContent = Get-Content $errorLogFile -Raw -ErrorAction SilentlyContinue
                if ($errorContent -and $errorContent.Trim()) {
                    Write-Host "`nErrors from startup_errors.log:" -ForegroundColor Yellow
                    Get-Content $errorLogFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
                }
            }

            if (Test-Path $logFile) {
                $logContent = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
                if ($logContent -and $logContent.Trim()) {
                    Write-Host "`nOutput from startup.log:" -ForegroundColor Yellow
                    Get-Content $logFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
                }
            }

            Stop-Services
            exit 1
        }

        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $backendReady = $true
                break
            }
        } catch {
            # Also check if port is listening as fallback
            $portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
            if ($portCheck) {
                $backendReady = $true
                break
            }
        }
        Start-Sleep -Seconds 1
        $attempt++
    }

    if (-not $backendReady) {
        Write-ErrorMsg "Backend failed to start within 30 seconds"
        Write-Host "`nDiagnostics:" -ForegroundColor Yellow
        Write-Host "  Process alive: $(if (Get-Process -Id $script:BackendProcess.Id -ErrorAction SilentlyContinue) {'Yes'} else {'No'})" -ForegroundColor Gray
        Write-Host "  Port 8000 listening: $(if (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue) {'Yes'} else {'No'})" -ForegroundColor Gray

        if (Test-Path $errorLogFile) {
            $errorContent = Get-Content $errorLogFile -Raw -ErrorAction SilentlyContinue
            if ($errorContent -and $errorContent.Trim()) {
                Write-Host "`nErrors from startup_errors.log:" -ForegroundColor Yellow
                Get-Content $errorLogFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
        }

        if (Test-Path $logFile) {
            $logContent = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
            if ($logContent -and $logContent.Trim()) {
                Write-Host "`nOutput from startup.log:" -ForegroundColor Yellow
                Get-Content $logFile -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            }
        }

        Stop-Services
        exit 1
    }

    Write-Success "Backend running on http://localhost:8000"
} catch {
    Set-Location ..
    Write-ErrorMsg "Failed to start backend: $_"
    Stop-Services
    exit 1
}

# Start frontend
Write-Progress "Starting frontend..."
try {
    $frontendPath = Join-Path $PWD "frontend"
    $frontendLogFile = Join-Path $frontendPath "startup.log"

    # Start frontend with visible console by default, or quiet mode with logs only
    if ($Quiet) {
        # Quiet mode: minimize window, log to file only
        $script:FrontendProcess = Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev 2>&1 | Tee-Object -FilePath 'startup.log'" `
            -WorkingDirectory $frontendPath `
            -PassThru `
            -WindowStyle Minimized
    } else {
        # Default: Show console and also log to file
        $script:FrontendProcess = Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev 2>&1 | Tee-Object -FilePath 'startup.log'" `
            -WorkingDirectory $frontendPath `
            -PassThru `
            -WindowStyle Normal
    }

    # Give the process a moment to start
    Start-Sleep -Seconds 2

    # Check if process is still alive
    if (-not (Get-Process -Id $script:FrontendProcess.Id -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "Frontend process crashed immediately after startup"
        Write-Host "`nLast 20 lines of startup.log:" -ForegroundColor Yellow
        Get-Content $frontendLogFile -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        Stop-Services
        exit 1
    }

    # Wait for frontend to be ready
    $maxAttempts = 30
    $attempt = 0
    $frontendReady = $false

    while ($attempt -lt $maxAttempts) {
        # Check if process is still alive
        if (-not (Get-Process -Id $script:FrontendProcess.Id -ErrorAction SilentlyContinue)) {
            Write-ErrorMsg "Frontend process died during startup (attempt $attempt)"
            Write-Host "`nLast 20 lines of startup.log:" -ForegroundColor Yellow
            Get-Content $frontendLogFile -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
            Stop-Services
            exit 1
        }

        try {
            $connection = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
            if ($connection) {
                $frontendReady = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 1
        $attempt++
    }

    if (-not $frontendReady) {
        Write-ErrorMsg "Frontend failed to start within 30 seconds"
        Write-Host "`nDiagnostics:" -ForegroundColor Yellow
        Write-Host "  Process alive: $(if (Get-Process -Id $script:FrontendProcess.Id -ErrorAction SilentlyContinue) {'Yes'} else {'No'})" -ForegroundColor Gray
        Write-Host "  Port 5173 listening: $(if (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue) {'Yes'} else {'No'})" -ForegroundColor Gray
        Write-Host "`nLast 20 lines of startup.log:" -ForegroundColor Yellow
        Get-Content $frontendLogFile -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        Stop-Services
        exit 1
    }

    Write-Success "Frontend running on http://localhost:5173"
} catch {
    Set-Location ..
    Write-ErrorMsg "Failed to start frontend: $_"
    Stop-Services
    exit 1
}

# Open browser
if (-not $SkipBrowser) {
    Write-Host "`n[INFO] Opening Portfolio Manager in browser..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5173"
}

Write-Host "`n[OK] Application ready!`n" -ForegroundColor Green
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Gray
Write-Host "Frontend UI: http://localhost:5173" -ForegroundColor Gray
Write-Host "API Docs: http://localhost:8000/docs`n" -ForegroundColor Gray

Write-Host "Press Ctrl+C to stop all services...`n" -ForegroundColor Yellow

# Keep script running
try {
    while ($true) {
        Start-Sleep -Seconds 1

        # Check if processes are still running
        if (-not (Get-Process -Id $script:BackendProcess.Id -ErrorAction SilentlyContinue)) {
            Write-ErrorMsg "Backend process died unexpectedly"
            Stop-Services
            exit 1
        }

        if (-not (Get-Process -Id $script:FrontendProcess.Id -ErrorAction SilentlyContinue)) {
            Write-ErrorMsg "Frontend process died unexpectedly"
            Stop-Services
            exit 1
        }
    }
} finally {
    Stop-Services
}

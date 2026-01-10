# Portfolio Manager - Startup Script
# Handles both first-time setup and subsequent launches

param(
    [switch]$SkipBrowser
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
    Write-Success "Python $pythonVersion found"
} catch {
    Write-ErrorMsg "Python not found!"
    Write-Host "Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Node.js
try {
    $nodeVersion = (node --version) -replace "v", ""
    Write-Success "Node.js $nodeVersion found"
} catch {
    Write-ErrorMsg "Node.js not found!"
    Write-Host "Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
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

# Check if port 8000 is in use
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000InUse) {
    Write-ErrorMsg "Port 8000 is already in use!"
    Write-Host "Please stop the existing service or change the port in backend/main.py" -ForegroundColor Yellow
    exit 1
}

# Check if port 5173 is in use
$port5173InUse = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173InUse) {
    Write-ErrorMsg "Port 5173 is already in use!"
    Write-Host "Please stop the existing service" -ForegroundColor Yellow
    exit 1
}

# Start backend
Write-Progress "Starting backend API..."
try {
    Set-Location backend
    $script:BackendProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
        -PassThru `
        -WindowStyle Minimized
    Set-Location ..

    # Give the process a moment to start
    Start-Sleep -Seconds 2

    # Wait for backend to be ready
    $maxAttempts = 30
    $attempt = 0
    $backendReady = $false

    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $backendReady = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
            $attempt++
        }
    }

    if (-not $backendReady) {
        Write-ErrorMsg "Backend failed to start within 30 seconds"
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
    Set-Location frontend
    $script:FrontendProcess = Start-Process -FilePath "npm" `
        -ArgumentList "run", "dev" `
        -PassThru `
        -WindowStyle Minimized
    Set-Location ..

    # Give the process a moment to start
    Start-Sleep -Seconds 2

    # Wait for frontend to be ready
    $maxAttempts = 30
    $attempt = 0
    $frontendReady = $false

    while ($attempt -lt $maxAttempts) {
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

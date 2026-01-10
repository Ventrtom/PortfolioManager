# Portfolio Manager - End-to-End Test Script
# Tests the complete application startup and basic functionality

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

# Change to script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Test results tracking
$script:TestsPassed = 0
$script:TestsFailed = 0
$script:TestResults = @()

# Color functions
function Write-TestHeader { param($msg) Write-Host "`n========================================" -ForegroundColor Magenta; Write-Host $msg -ForegroundColor Magenta; Write-Host "========================================`n" -ForegroundColor Magenta }
function Write-TestSection { param($msg) Write-Host "`n[TEST SECTION] $msg" -ForegroundColor Cyan }
function Write-TestCase { param($msg) Write-Host "  [TEST] $msg" -ForegroundColor Yellow }
function Write-TestPass { param($msg) Write-Host "    [PASS] $msg" -ForegroundColor Green; $script:TestsPassed++ }
function Write-TestFail { param($msg) Write-Host "    [FAIL] $msg" -ForegroundColor Red; $script:TestsFailed++ }
function Write-TestInfo { param($msg) if ($Verbose) { Write-Host "    [INFO] $msg" -ForegroundColor Gray } }

# Helper function to record test results
function Record-TestResult {
    param($TestName, $Passed, $Message)
    $script:TestResults += [PSCustomObject]@{
        TestName = $TestName
        Passed = $Passed
        Message = $Message
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
}

Write-TestHeader "Portfolio Manager - End-to-End Tests"

# ============================================================================
# SECTION 1: Prerequisites Check
# ============================================================================
Write-TestSection "1. Prerequisites Check"

Write-TestCase "Python installation"
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-TestPass "Python found: $pythonVersion"
        Record-TestResult "Python Installation" $true $pythonVersion
    } else {
        Write-TestFail "Python not found"
        Record-TestResult "Python Installation" $false "Python not found"
    }
} catch {
    Write-TestFail "Python check failed: $_"
    Record-TestResult "Python Installation" $false $_
}

Write-TestCase "Node.js installation"
try {
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-TestPass "Node.js found: $nodeVersion"
        Record-TestResult "Node.js Installation" $true $nodeVersion
    } else {
        Write-TestFail "Node.js not found"
        Record-TestResult "Node.js Installation" $false "Node.js not found"
    }
} catch {
    Write-TestFail "Node.js check failed: $_"
    Record-TestResult "Node.js Installation" $false $_
}

Write-TestCase "npm installation"
try {
    $npmVersion = npm --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-TestPass "npm found: $npmVersion"
        Record-TestResult "npm Installation" $true $npmVersion
    } else {
        Write-TestFail "npm not found"
        Record-TestResult "npm Installation" $false "npm not found"
    }
} catch {
    Write-TestFail "npm check failed: $_"
    Record-TestResult "npm Installation" $false $_
}

# ============================================================================
# SECTION 2: Project Structure
# ============================================================================
Write-TestSection "2. Project Structure"

Write-TestCase "Backend directory structure"
$backendPaths = @(
    "backend\main.py",
    "backend\requirements.txt",
    "backend\models\database.py",
    "backend\models\schemas.py",
    "backend\services",
    "backend\routes",
    "backend\utils"
)
$allBackendPathsExist = $true
foreach ($path in $backendPaths) {
    if (Test-Path $path) {
        Write-TestInfo "Found: $path"
    } else {
        Write-TestFail "Missing: $path"
        Record-TestResult "Backend Structure: $path" $false "Path not found"
        $allBackendPathsExist = $false
    }
}
if ($allBackendPathsExist) {
    Write-TestPass "All backend paths exist"
    Record-TestResult "Backend Structure" $true "All paths exist"
}

Write-TestCase "Frontend directory structure"
$frontendPaths = @(
    "frontend\package.json",
    "frontend\vite.config.ts",
    "frontend\src\App.tsx",
    "frontend\src\components",
    "frontend\src\api",
    "frontend\src\types"
)
$allFrontendPathsExist = $true
foreach ($path in $frontendPaths) {
    if (Test-Path $path) {
        Write-TestInfo "Found: $path"
    } else {
        Write-TestFail "Missing: $path"
        Record-TestResult "Frontend Structure: $path" $false "Path not found"
        $allFrontendPathsExist = $false
    }
}
if ($allFrontendPathsExist) {
    Write-TestPass "All frontend paths exist"
    Record-TestResult "Frontend Structure" $true "All paths exist"
}

Write-TestCase "Startup scripts"
$scripts = @("start.ps1", "stop.ps1", "start.bat")
$allScriptsExist = $true
foreach ($script in $scripts) {
    if (Test-Path $script) {
        Write-TestInfo "Found: $script"
    } else {
        Write-TestFail "Missing: $script"
        Record-TestResult "Startup Script: $script" $false "Script not found"
        $allScriptsExist = $false
    }
}
if ($allScriptsExist) {
    Write-TestPass "All startup scripts exist"
    Record-TestResult "Startup Scripts" $true "All scripts exist"
}

# ============================================================================
# SECTION 3: Dependencies
# ============================================================================
Write-TestSection "3. Dependencies"

Write-TestCase "Backend virtual environment"
if (Test-Path "backend\venv") {
    Write-TestPass "Virtual environment exists"
    Record-TestResult "Backend venv" $true "Virtual environment found"

    # Check if Python executable exists in venv
    if (Test-Path "backend\venv\Scripts\python.exe") {
        Write-TestInfo "Python executable found in venv"
    } else {
        Write-TestFail "Python executable not found in venv"
        Record-TestResult "Backend venv Python" $false "Python.exe not found"
    }
} else {
    Write-TestFail "Virtual environment does not exist"
    Record-TestResult "Backend venv" $false "Virtual environment not found"
}

Write-TestCase "Frontend node_modules"
if (Test-Path "frontend\node_modules") {
    Write-TestPass "node_modules exists"
    Record-TestResult "Frontend node_modules" $true "node_modules found"

    # Check for key dependencies
    $keyDeps = @("react", "vite", "axios", "chart.js")
    foreach ($dep in $keyDeps) {
        if (Test-Path "frontend\node_modules\$dep") {
            Write-TestInfo "Dependency found: $dep"
        } else {
            Write-TestFail "Missing dependency: $dep"
            Record-TestResult "Frontend dependency: $dep" $false "Dependency not found"
        }
    }
} else {
    Write-TestFail "node_modules does not exist"
    Record-TestResult "Frontend node_modules" $false "node_modules not found"
}

# ============================================================================
# SECTION 4: Service Startup
# ============================================================================
Write-TestSection "4. Service Startup"

# Check if services are already running
$existingBackend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$existingFrontend = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue

if ($existingBackend -or $existingFrontend) {
    Write-Host "`n[WARNING] Services are already running. Stopping them first..." -ForegroundColor Yellow
    & "$ScriptDir\stop.ps1"
    Start-Sleep -Seconds 2
}

Write-TestCase "Starting backend service"
try {
    $backendPath = Join-Path $PWD "backend"
    $backendProcess = Start-Process -FilePath "$backendPath\venv\Scripts\python.exe" `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $backendPath `
        -PassThru `
        -WindowStyle Hidden

    Start-Sleep -Seconds 3

    # Check if backend is responding
    $maxAttempts = 15
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

    if ($backendReady) {
        Write-TestPass "Backend started successfully on port 8000"
        Record-TestResult "Backend Startup" $true "Backend running on port 8000"
    } else {
        Write-TestFail "Backend failed to start within 15 seconds"
        Record-TestResult "Backend Startup" $false "Timeout waiting for backend"
    }
} catch {
    Write-TestFail "Backend startup failed: $_"
    Record-TestResult "Backend Startup" $false $_
}

Write-TestCase "Starting frontend service"
try {
    $frontendPath = Join-Path $PWD "frontend"
    $frontendProcess = Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoExit", "-WindowStyle", "Hidden", "-Command", "cd '$frontendPath'; npm run dev" `
        -WorkingDirectory $frontendPath `
        -PassThru `
        -WindowStyle Hidden

    Start-Sleep -Seconds 5

    # Check if frontend is responding
    $maxAttempts = 20
    $attempt = 0
    $frontendReady = $false

    while ($attempt -lt $maxAttempts) {
        $connection = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
        if ($connection) {
            $frontendReady = $true
            break
        }
        Start-Sleep -Seconds 1
        $attempt++
    }

    if ($frontendReady) {
        Write-TestPass "Frontend started successfully on port 5173"
        Record-TestResult "Frontend Startup" $true "Frontend running on port 5173"
    } else {
        Write-TestFail "Frontend failed to start within 20 seconds"
        Record-TestResult "Frontend Startup" $false "Timeout waiting for frontend"
    }
} catch {
    Write-TestFail "Frontend startup failed: $_"
    Record-TestResult "Frontend Startup" $false $_
}

# ============================================================================
# SECTION 5: API Endpoint Tests
# ============================================================================
Write-TestSection "5. API Endpoint Tests"

Write-TestCase "Health endpoint"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-TestPass "Health endpoint responding (200 OK)"
        Record-TestResult "API Health Endpoint" $true "Status 200"
    } else {
        Write-TestFail "Health endpoint returned status: $($response.StatusCode)"
        Record-TestResult "API Health Endpoint" $false "Status $($response.StatusCode)"
    }
} catch {
    Write-TestFail "Health endpoint failed: $_"
    Record-TestResult "API Health Endpoint" $false $_
}

Write-TestCase "API documentation endpoint"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-TestPass "API docs endpoint responding (200 OK)"
        Record-TestResult "API Docs Endpoint" $true "Status 200"
    } else {
        Write-TestFail "API docs returned status: $($response.StatusCode)"
        Record-TestResult "API Docs Endpoint" $false "Status $($response.StatusCode)"
    }
} catch {
    Write-TestFail "API docs endpoint failed: $_"
    Record-TestResult "API Docs Endpoint" $false $_
}

Write-TestCase "Transactions endpoint"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/transactions/" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-TestPass "Transactions endpoint responding (200 OK)"
        Record-TestResult "API Transactions Endpoint" $true "Status 200"
    } else {
        Write-TestFail "Transactions endpoint returned status: $($response.StatusCode)"
        Record-TestResult "API Transactions Endpoint" $false "Status $($response.StatusCode)"
    }
} catch {
    Write-TestFail "Transactions endpoint failed: $_"
    Record-TestResult "API Transactions Endpoint" $false $_
}

Write-TestCase "Portfolio summary endpoint"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/portfolio/summary" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-TestPass "Portfolio summary endpoint responding (200 OK)"
        Record-TestResult "API Portfolio Summary" $true "Status 200"
    } else {
        Write-TestFail "Portfolio summary returned status: $($response.StatusCode)"
        Record-TestResult "API Portfolio Summary" $false "Status $($response.StatusCode)"
    }
} catch {
    Write-TestFail "Portfolio summary endpoint failed: $_"
    Record-TestResult "API Portfolio Summary" $false $_
}

# ============================================================================
# SECTION 6: Frontend Accessibility
# ============================================================================
Write-TestSection "6. Frontend Accessibility"

Write-TestCase "Frontend homepage"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-TestPass "Frontend homepage responding (200 OK)"
        Record-TestResult "Frontend Homepage" $true "Status 200"

        # Check if HTML contains expected elements
        if ($response.Content -match "Portfolio Manager") {
            Write-TestInfo "Page contains 'Portfolio Manager' title"
        } else {
            Write-TestFail "Page does not contain expected title"
            Record-TestResult "Frontend Content" $false "Missing title"
        }
    } else {
        Write-TestFail "Frontend returned status: $($response.StatusCode)"
        Record-TestResult "Frontend Homepage" $false "Status $($response.StatusCode)"
    }
} catch {
    Write-TestFail "Frontend homepage failed: $_"
    Record-TestResult "Frontend Homepage" $false $_
}

# ============================================================================
# SECTION 7: Cleanup
# ============================================================================
Write-TestSection "7. Cleanup"

Write-TestCase "Stopping test services"
try {
    if ($backendProcess) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        Write-TestInfo "Backend process stopped"
    }

    if ($frontendProcess) {
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
        Write-TestInfo "Frontend process stopped"
    }

    # Clean up any remaining processes on ports
    Start-Sleep -Seconds 1

    $backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($backend) {
        Stop-Process -Id $backend.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    $frontend = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($frontend) {
        Stop-Process -Id $frontend.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    Write-TestPass "Services stopped successfully"
    Record-TestResult "Cleanup" $true "All services stopped"
} catch {
    Write-TestFail "Cleanup failed: $_"
    Record-TestResult "Cleanup" $false $_
}

# ============================================================================
# SECTION 8: Test Summary
# ============================================================================
Write-TestHeader "Test Summary"

$totalTests = $script:TestsPassed + $script:TestsFailed
$passRate = if ($totalTests -gt 0) { [math]::Round(($script:TestsPassed / $totalTests) * 100, 2) } else { 0 }

Write-Host "Total Tests: $totalTests" -ForegroundColor Cyan
Write-Host "Passed: $script:TestsPassed" -ForegroundColor Green
Write-Host "Failed: $script:TestsFailed" -ForegroundColor Red
Write-Host "Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -eq 100) { "Green" } elseif ($passRate -ge 80) { "Yellow" } else { "Red" })

# Export test results to JSON
$resultsFile = "test-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
$script:TestResults | ConvertTo-Json -Depth 10 | Out-File $resultsFile
Write-Host "`nDetailed results saved to: $resultsFile" -ForegroundColor Gray

# Exit with appropriate code
if ($script:TestsFailed -eq 0) {
    Write-Host "`n[SUCCESS] All tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n[FAILURE] Some tests failed. Please review the results above." -ForegroundColor Red
    exit 1
}

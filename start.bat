@echo off
SETLOCAL EnableDelayedExpansion

:: Portfolio Manager - Startup Script (Batch Version)
:: Handles both first-time setup and subsequent launches

title Portfolio Manager

echo.
echo ========================================
echo Portfolio Manager - Startup Script
echo ========================================
echo.

:: Check Python
echo [INFO] Checking prerequisites...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   [32m√[0m Python %PYTHON_VERSION% found

:: Check Node.js
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found!
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
for /f %%i in ('node --version') do set NODE_VERSION=%%i
echo   [32m√[0m Node.js %NODE_VERSION% found

:: Check npm
npm --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] npm not found!
    echo Please install npm (usually comes with Node.js)
    pause
    exit /b 1
)
for /f %%i in ('npm --version') do set NPM_VERSION=%%i
echo   [32m√[0m npm %NPM_VERSION% found

:: Check for first-time setup
set FIRST_TIME=0
if not exist "backend\venv" set FIRST_TIME=1
if not exist "frontend\node_modules" set FIRST_TIME=1

if %FIRST_TIME%==1 (
    echo.
    echo [INFO] First-time setup detected
    echo.
)

:: Backend setup
if not exist "backend\venv" (
    echo [INFO] Setting up backend...
    echo   [33m→[0m Creating virtual environment...
    cd backend
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment
        cd ..
        pause
        exit /b 1
    )
    echo   [32m√[0m Virtual environment created

    echo   [33m→[0m Installing Python dependencies...
    call venv\Scripts\pip.exe install --upgrade pip --quiet
    call venv\Scripts\pip.exe install -r requirements.txt --quiet
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Python dependencies
        cd ..
        pause
        exit /b 1
    )
    echo   [32m√[0m Backend setup complete
    cd ..
)

:: Frontend setup
if not exist "frontend\node_modules" (
    echo [INFO] Setting up frontend...
    echo   [33m→[0m Installing Node.js dependencies...
    cd frontend
    call npm install --silent >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Node.js dependencies
        cd ..
        pause
        exit /b 1
    )
    echo   [32m√[0m Frontend setup complete
    cd ..
)

:: Start services
echo.
echo [INFO] Starting services...

:: Start backend
echo   [33m→[0m Starting backend API...
cd backend
start /B "" venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
cd ..

:: Wait for backend
timeout /t 5 /nobreak >nul
echo   [32m√[0m Backend running on http://localhost:8000

:: Start frontend
echo   [33m→[0m Starting frontend...
cd frontend
start /B "" npm run dev
cd ..

:: Wait for frontend
timeout /t 5 /nobreak >nul
echo   [32m√[0m Frontend running on http://localhost:5173

:: Open browser
echo.
echo [INFO] Opening Portfolio Manager in browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173

:: Success message
echo.
echo [32m√ Application ready![0m
echo.
echo Backend API: http://localhost:8000
echo Frontend UI: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop (you may need to close processes manually)
echo or simply close this window when done.
echo.

:: Keep window open
pause

@echo off
title OneSmarter Admin Portal Launcher
color 0A

echo ======================================================================
echo             ONESMARTER ADMIN PORTAL - SYSTEM LAUNCHER
echo ======================================================================
echo.

:: 1. Verify Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Verify Node.js / NPM is installed
call npm --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Node.js / NPM is not installed or not in your system PATH.
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

echo [1/4] Checking and installing Python backend requirements...
cd /d "%~dp0django_backend"
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies failed to install via pip. Trying to continue...
)

echo [2/4] Initializing Database, running migrations and seeding data...
python manage.py migrate --noinput
python manage.py seed_data

echo.
echo [3/4] Checking and installing Frontend dependencies...
cd /d "%~dp0frontend_react"
if not exist "node_modules\" (
    echo Installing node_modules (first run, may take a moment)...
    call npm install
)

echo.
echo [4/4] Starting Django Backend and Vite Frontend servers...

:: Launch Django Backend in a separate window
start "OneSmarter Backend (Django :8000)" cmd /k "cd /d %~dp0django_backend && python manage.py runserver 127.0.0.1:8000"

:: Launch Vite React Frontend in a separate window
start "OneSmarter Frontend (React :5173)" cmd /k "cd /d %~dp0frontend_react && npm run dev"

echo.
echo ======================================================================
echo  Portal successfully started!
echo  - Django Backend:  http://127.0.0.1:8000/api/health/
echo  - React Frontend:  http://localhost:5173/
echo.
echo  Default Admin Credentials:
echo    Username: admin
echo    Password: password123
echo ======================================================================
echo.

:: Wait 3 seconds for Vite server to spin up, then open default browser
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo Servers are running in the opened background windows.
echo You can close this launcher window anytime.
pause

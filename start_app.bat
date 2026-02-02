@echo off
setlocal

echo ==========================================
echo Starting Prompt Compiler Dev Environment
echo ==========================================

:: check for node
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

:: check for python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Activate Backend Environment
echo.
echo [BACKEND] Checking for virtual environment...
if exist ".venv\Scripts\activate.bat" (
    echo [BACKEND] Activating .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] .venv not found! Using system python.
    echo To create one: python -m venv .venv
)

:: Start Backend (Port 8080)
echo.
echo [BACKEND] Starting FastAPI server on port 8080...
start "Backend (FastAPI)" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn api.main:app --reload --port 8080"

:: Start Frontend
echo.
echo [FRONTEND] Starting Next.js dev server...
cd web
if not exist "node_modules" (
    echo [FRONTEND] node_modules not found. Running npm install...
    call npm install
)
start "Frontend (Next.js)" cmd /k "npm run dev"

echo.
echo ==========================================
echo Servers started successfully!
echo Backend:  http://localhost:8080/docs
echo Frontend: http://localhost:3000
echo ==========================================
echo.

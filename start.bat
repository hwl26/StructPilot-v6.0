@echo off
chcp 65001 >nul
setlocal
title StructPilot v6.0 - Cryo-EM Pipeline Copilot

echo ============================================
echo   StructPilot v6.0  Cryo-EM Pipeline Copilot
echo ============================================
echo.

REM Check .venv
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] First run, creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Please install Python 3.10+ first.
        pause
        exit /b 1
    )
    echo [INFO] Upgrading pip...
    call .venv\Scripts\python.exe -m pip install --upgrade pip
    echo [INFO] Installing dependencies...
    call .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [INFO] Running health check...
call .venv\Scripts\python.exe healthcheck.py
if errorlevel 1 (
    echo.
    echo [WARN] Health check reported a problem.
    echo [WARN] You can still inspect the messages above, then rerun start.bat after fixing them.
    pause
    exit /b 1
)

echo [INFO] Starting StructPilot...
echo [INFO] Please open http://localhost:8501 in your browser
echo.
echo Press Ctrl+C to stop the server
echo.

call .venv\Scripts\python.exe -m streamlit run main.py --server.port 8501

pause

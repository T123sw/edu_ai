@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo    RAG API service startup script
echo ========================================
echo.

cd /d %~dp0

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    echo Detected local virtual environment: %PYTHON_EXE%
    REM Validate the venv before using it. A copied or stale venv can exist
    REM even when its base Python installation has been removed.
    "%PYTHON_EXE%" -c "import ctypes, sys; print(sys.base_prefix)" >nul 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo Local virtual environment is unhealthy. Falling back to system Python.
        set "PYTHON_EXE=python"
    )
) else (
    echo Local virtual environment not found. Falling back to system Python.
    set "PYTHON_EXE=python"
)
echo.

set "PORT=8001"

echo [1/3] Checking whether port %PORT% is in use...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo Warning: port %PORT% is already in use. Trying to stop the process...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
        echo Found process ID: %%a
        taskkill /F /PID %%a >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            echo Process stopped.
            timeout /t 2 /nobreak >nul
        ) else (
            echo Could not stop process. You may need administrator rights.
        )
    )
) else (
    echo Port %PORT% is available.
)
echo.

echo [2/3] Checking dependencies...
"%PYTHON_EXE%" -c "import uvicorn" >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo Uvicorn not found. Trying to install required packages...
    "%PYTHON_EXE%" -m pip install uvicorn fastapi
)
echo.

echo [3/3] Starting service...
echo ========================================
echo API service will run at: http://localhost:%PORT%
echo Press Ctrl+C to stop the service
echo ========================================
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

pause

@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo    Edu-AI API service startup script
echo ========================================
echo.

cd /d %~dp0

set "PYTHON_EXE=python"

REM ---- 1) local venvs (highest priority - most isolated) ----
for %%P in ("%~dp0.venv\Scripts\python.exe" "%~dp0.venv_local\Scripts\python.exe") do (
    if exist "%%~fP" (
        echo Detected local virtual environment: %%~fP
        "%%~fP" -c "import pip, ctypes, sys; print(sys.base_prefix)" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON_EXE=%%~fP"
            goto :python_ready
        ) else (
            echo Local virtual environment is unhealthy. Trying next.
        )
    )
)

REM ---- 2) conda edu-ai environment ----
for %%D in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "C:\ProgramData\miniconda3" "C:\ProgramData\anaconda3") do (
    if exist "%%~fD\envs\edu-ai\python.exe" (
        echo Detected conda edu-ai environment: %%~fD\envs\edu-ai\python.exe
        "%%~fD\envs\edu-ai\python.exe" -c "import pip, ctypes, sys; print(sys.base_prefix)" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON_EXE=%%~fD\envs\edu-ai\python.exe"
            goto :python_ready
        ) else (
            echo Conda edu-ai environment is unhealthy. Trying next.
        )
    )
)

echo No healthy Python environment found. Falling back to system python.

:python_ready
echo Using Python: %PYTHON_EXE%
echo.

echo Clearing proxy environment variables for backend startup...
for %%V in (HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy GIT_HTTP_PROXY GIT_HTTPS_PROXY) do (
    set "%%V="
)
echo.

set "PORT=8001"
set "PPT_PORT=46080"
set "PPT_DIR=%~dp0modules\html2ppt"

echo [1/4] Checking whether port %PORT% is in use...
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

echo [2/4] Checking PPT engine...
if exist "%PPT_DIR%\package.json" (
    netstat -ano | findstr ":%PPT_PORT%" | findstr "LISTENING" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo PPT engine is already listening on port %PPT_PORT%.
    ) else (
        echo PPT engine is not running. Starting html2ppt service...
        start "html2ppt-service" /D "%PPT_DIR%" cmd /k npm start
        timeout /t 5 /nobreak >nul
        netstat -ano | findstr ":%PPT_PORT%" | findstr "LISTENING" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            echo PPT engine started on http://127.0.0.1:%PPT_PORT%
        ) else (
            echo Warning: html2ppt service did not start listening on port %PPT_PORT%.
            echo You can inspect the "html2ppt-service" window or run:
            echo   cd /d "%PPT_DIR%" ^&^& npm start
        )
    )
) else (
    echo Warning: html2ppt package.json not found at "%PPT_DIR%".
)
echo.

echo [3/4] Checking dependencies...
"%PYTHON_EXE%" -c "import uvicorn" >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo Uvicorn not found. Trying to install required packages...
    "%PYTHON_EXE%" -m pip install uvicorn fastapi
)
echo.

echo [4/4] Starting service...
echo ========================================
echo API service will run at: http://localhost:%PORT%
echo PPT service is expected at: http://127.0.0.1:%PPT_PORT%
echo Press Ctrl+C to stop the service
echo ========================================
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

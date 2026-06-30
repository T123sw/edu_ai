@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo    Edu-AI full stack startup script
echo ========================================
echo.

set "API_DIR=%~dp0"
for %%I in ("%API_DIR%..\..") do set "FRONTEND_DIR=%%~fI"
cd /d "%API_DIR%"

set "PYTHON_EXE=python"
set "CONDA_ENV_DIR="

REM ---- 1) local venvs (highest priority - most isolated) ----
for %%P in ("%API_DIR%.venv\Scripts\python.exe" "%API_DIR%.venv_local\Scripts\python.exe") do (
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
for %%D in ("D:\anaconda" "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "C:\ProgramData\miniconda3" "C:\ProgramData\anaconda3") do (
    if exist "%%~fD\envs\edu-ai\python.exe" (
        echo Detected conda edu-ai environment: %%~fD\envs\edu-ai\python.exe
        "%%~fD\envs\edu-ai\python.exe" -c "import pip, ctypes, sys; print(sys.base_prefix)" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            set "CONDA_ENV_DIR=%%~fD\envs\edu-ai"
            set "PYTHON_EXE=%%~fD\envs\edu-ai\python.exe"
            goto :python_ready
        ) else (
            echo Conda edu-ai environment is unhealthy. Trying next.
        )
    )
)

echo No healthy Python environment found. Falling back to system python.

:python_ready
if defined CONDA_ENV_DIR (
    set "CONDA_DEFAULT_ENV=edu-ai"
    set "CONDA_PREFIX=%CONDA_ENV_DIR%"
    set "PATH=%CONDA_ENV_DIR%;%CONDA_ENV_DIR%\Scripts;%CONDA_ENV_DIR%\Library\bin;%PATH%"
)

echo Using Python: %PYTHON_EXE%
echo Frontend directory: %FRONTEND_DIR%
echo API directory: %API_DIR%
echo.

if /I "%~1"=="--check" (
    if not exist "%FRONTEND_DIR%\package.json" (
        echo [ERROR] Frontend package.json not found: "%FRONTEND_DIR%\package.json"
        exit /b 1
    )
    if not exist "%API_DIR%app\main.py" (
        echo [ERROR] Backend app entry not found: "%API_DIR%app\main.py"
        exit /b 1
    )
    echo Startup script check passed.
    exit /b 0
)

echo Clearing proxy environment variables for local startup...
for %%V in (HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy GIT_HTTP_PROXY GIT_HTTPS_PROXY) do (
    set "%%V="
)
echo.

set "API_PORT=8001"
set "FRONTEND_PORT=5173"
set "PPT_PORT=46080"
set "PPT_DIR=%API_DIR%modules\html2ppt"
set "VITE_API_BASE_URL=http://localhost:%API_PORT%"
set "VITE_PPT_BASE_URL=http://127.0.0.1:%PPT_PORT%"

echo [1/6] Checking ports...
call :ensure_port_free "%API_PORT%" "API"
call :ensure_port_free "%FRONTEND_PORT%" "frontend"
echo.

echo [2/6] Checking backend dependencies...
"%PYTHON_EXE%" -c "import uvicorn, fastapi" >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo Uvicorn/FastAPI not found. Installing minimal backend packages...
    "%PYTHON_EXE%" -m pip install uvicorn fastapi
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Backend dependency installation failed.
        pause
        exit /b 1
    )
)
echo Backend dependencies look available.
echo.

echo [3/6] Checking frontend dependencies...
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend package.json not found: "%FRONTEND_DIR%\package.json"
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Frontend node_modules not found. Running npm install...
    pushd "%FRONTEND_DIR%"
    call npm.cmd install
    set "NPM_RESULT=!ERRORLEVEL!"
    popd
    if !NPM_RESULT! NEQ 0 (
        echo [ERROR] Frontend npm install failed.
        pause
        exit /b 1
    )
) else (
    echo Frontend node_modules found.
)
echo.

echo [4/6] Checking PPT engine...
if exist "%PPT_DIR%\package.json" (
    if not exist "%PPT_DIR%\node_modules" (
        echo html2ppt node_modules not found. Running npm install...
        pushd "%PPT_DIR%"
        call npm.cmd install
        set "PPT_NPM_RESULT=!ERRORLEVEL!"
        popd
        if !PPT_NPM_RESULT! NEQ 0 (
            echo [ERROR] html2ppt npm install failed.
            pause
            exit /b 1
        )
    )

    netstat -ano | findstr ":%PPT_PORT%" | findstr "LISTENING" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo PPT engine is already listening on port %PPT_PORT%.
    ) else (
        echo Starting html2ppt service...
        start "html2ppt-service" /D "%PPT_DIR%" cmd /k "npm.cmd start"
    )
) else (
    echo Warning: html2ppt package.json not found at "%PPT_DIR%".
)
echo.

echo [5/6] Starting frontend...
start "edu-ai-frontend" /D "%FRONTEND_DIR%" cmd /k "npm.cmd run dev -- --host 0.0.0.0 --port %FRONTEND_PORT%"
echo Frontend will run at: http://localhost:%FRONTEND_PORT%
echo Frontend API base: %VITE_API_BASE_URL%
echo.

echo [6/6] Starting backend API...
echo ========================================
echo API service:      http://localhost:%API_PORT%
echo Frontend:         http://localhost:%FRONTEND_PORT%
echo PPT service:      http://127.0.0.1:%PPT_PORT%
echo.
echo Close the opened terminal windows to stop frontend/PPT services.
echo Press Ctrl+C in this window to stop the backend.
echo ========================================
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %API_PORT%
pause
exit /b %ERRORLEVEL%

:ensure_port_free
set "CHECK_PORT=%~1"
set "CHECK_NAME=%~2"
netstat -ano | findstr ":%CHECK_PORT%" | findstr "LISTENING" >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo %CHECK_NAME% port %CHECK_PORT% is already in use. Trying to stop the process...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%CHECK_PORT%" ^| findstr "LISTENING"') do (
        echo Found process ID: %%a
        taskkill /F /PID %%a >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            echo Process %%a stopped.
            timeout /t 2 /nobreak >nul
        ) else (
            echo Warning: could not stop process %%a. You may need administrator rights.
        )
    )
) else (
    echo %CHECK_NAME% port %CHECK_PORT% is available.
)
exit /b 0

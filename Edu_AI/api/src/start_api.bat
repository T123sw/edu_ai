@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo    Edu-AI full stack startup script
echo ========================================
echo.

set "API_DIR=%~dp0"
for %%I in ("%API_DIR%..\..") do set "FRONTEND_DIR=%%~fI"
for %%I in ("%FRONTEND_DIR%\..") do set "REPO_ROOT=%%~fI"
set "SIDECAR_DIR=%REPO_ROOT%\openmaic-sidecar"
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
echo OpenMAIC sidecar directory: %SIDECAR_DIR%
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
    if not exist "%SIDECAR_DIR%\package.json" (
        echo [ERROR] OpenMAIC package.json not found: "%SIDECAR_DIR%\package.json"
        exit /b 1
    )
    if not exist "%SIDECAR_DIR%\app\api\health\route.ts" (
        echo [ERROR] OpenMAIC health endpoint not found: "%SIDECAR_DIR%\app\api\health\route.ts"
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
set "SIDECAR_PORT=3000"
set "VITE_API_BASE_URL=http://localhost:%API_PORT%"
set "CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
set "FRONTEND_VITE_CMD=%FRONTEND_DIR%\node_modules\.bin\vite.cmd"

echo [1/7] Checking Edu-AI ports...
call :ensure_port_free "%API_PORT%" "API"
call :ensure_port_free "%FRONTEND_PORT%" "frontend"
echo.

echo [2/7] Checking backend dependencies...
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

echo [3/7] Checking frontend dependencies...
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend package.json not found: "%FRONTEND_DIR%\package.json"
    pause
    exit /b 1
)
if not exist "%FRONTEND_VITE_CMD%" (
    echo Frontend Vite launcher not found. Running npm install...
    pushd "%FRONTEND_DIR%"
    call npm.cmd install
    set "NPM_RESULT=!ERRORLEVEL!"
    popd
    if !NPM_RESULT! NEQ 0 (
        echo [ERROR] Frontend npm install failed.
        pause
        exit /b 1
    )
    if not exist "%FRONTEND_VITE_CMD%" (
        echo [ERROR] Frontend Vite launcher is still missing after npm install.
        pause
        exit /b 1
    )
) else (
    echo Frontend Vite launcher found.
)
echo.

echo [4/7] Checking OpenMAIC dependencies...
if not exist "%SIDECAR_DIR%\package.json" (
    echo [ERROR] OpenMAIC package.json not found: "%SIDECAR_DIR%\package.json"
    pause
    exit /b 1
)
if not exist "%SIDECAR_DIR%\.env" if not exist "%SIDECAR_DIR%\.env.local" (
    echo [ERROR] OpenMAIC requires "%SIDECAR_DIR%\.env" or ".env.local".
    pause
    exit /b 1
)

where pnpm.cmd >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    for %%P in (
        "D:\anaconda\envs\openmaic\pnpm.cmd"
        "%USERPROFILE%\miniconda3\envs\openmaic\pnpm.cmd"
        "%USERPROFILE%\anaconda3\envs\openmaic\pnpm.cmd"
    ) do (
        if exist "%%~fP" (
            set "PATH=%%~dpP;%PATH%"
            goto :pnpm_ready
        )
    )
    echo [ERROR] pnpm.cmd was not found. Install pnpm 10 or the openmaic conda environment.
    pause
    exit /b 1
)

:pnpm_ready
call pnpm.cmd --version >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] pnpm.cmd is present but cannot run.
    pause
    exit /b 1
)

if not exist "%SIDECAR_DIR%\node_modules" (
    echo OpenMAIC node_modules not found. Running pnpm install...
    pushd "%SIDECAR_DIR%"
    call pnpm.cmd install
    set "PNPM_RESULT=!ERRORLEVEL!"
    popd
    if !PNPM_RESULT! NEQ 0 (
        echo [ERROR] OpenMAIC dependency installation failed.
        pause
        exit /b 1
    )
)
echo OpenMAIC dependencies look available.
echo.

echo [5/7] Starting OpenMAIC sidecar...
call :sidecar_health
if !ERRORLEVEL! EQU 0 (
    echo OpenMAIC sidecar is already healthy at http://localhost:%SIDECAR_PORT%.
) else (
    netstat -ano | findstr ":%SIDECAR_PORT%" | findstr "LISTENING" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo [ERROR] Sidecar port %SIDECAR_PORT% is occupied, but /api/health is not healthy.
        echo Refusing to stop an unknown process. Free the port and run this script again.
        pause
        exit /b 1
    )

    start "edu-ai-openmaic-sidecar" /D "%SIDECAR_DIR%" cmd /k "set PORT=%SIDECAR_PORT%&&pnpm.cmd dev"
    call :wait_for_sidecar
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] OpenMAIC sidecar did not become healthy within 90 seconds.
        echo Check the "edu-ai-openmaic-sidecar" terminal for the startup error.
        pause
        exit /b 1
    )
    echo OpenMAIC sidecar is healthy at http://localhost:%SIDECAR_PORT%.
)
echo.

echo [6/7] Starting frontend...
start "edu-ai-frontend" /D "%FRONTEND_DIR%" cmd /k "npm.cmd run dev -- --host 0.0.0.0 --port %FRONTEND_PORT%"
call :wait_for_frontend
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Frontend did not become ready within 90 seconds.
    echo Check the "edu-ai-frontend" terminal for the startup error.
    pause
    exit /b 1
)
echo Frontend is ready at http://localhost:%FRONTEND_PORT%.
echo Frontend will run at: http://localhost:%FRONTEND_PORT%
echo Frontend API base: %VITE_API_BASE_URL%
echo.

echo [7/7] Starting backend API...
echo ========================================
echo API service:      http://localhost:%API_PORT%
echo Frontend:         http://localhost:%FRONTEND_PORT%
echo OpenMAIC sidecar: http://localhost:%SIDECAR_PORT%
echo.
echo Close the opened terminal windows to stop the frontend and OpenMAIC.
echo Press Ctrl+C in this window to stop the backend.
echo ========================================
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %API_PORT%
pause
exit /b %ERRORLEVEL%

:sidecar_health
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
    "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%SIDECAR_PORT%/api/health' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" ^
    >nul 2>nul
exit /b %ERRORLEVEL%

:wait_for_sidecar
set "SIDECAR_HEALTH_ATTEMPTS=0"

:wait_for_sidecar_loop
call :sidecar_health
if !ERRORLEVEL! EQU 0 exit /b 0
set /a SIDECAR_HEALTH_ATTEMPTS+=1
if !SIDECAR_HEALTH_ATTEMPTS! GEQ 45 exit /b 1
timeout /t 2 /nobreak >nul
goto :wait_for_sidecar_loop

:frontend_health
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
    "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%FRONTEND_PORT%/' -TimeoutSec 2; if ($response.StatusCode -lt 500) { exit 0 } } catch {}; exit 1" ^
    >nul 2>nul
exit /b %ERRORLEVEL%

:wait_for_frontend
set "FRONTEND_HEALTH_ATTEMPTS=0"

:wait_for_frontend_loop
call :frontend_health
if !ERRORLEVEL! EQU 0 exit /b 0
set /a FRONTEND_HEALTH_ATTEMPTS+=1
if !FRONTEND_HEALTH_ATTEMPTS! GEQ 45 exit /b 1
timeout /t 2 /nobreak >nul
goto :wait_for_frontend_loop

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

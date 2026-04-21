@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d %~dp0

set "PYTHON_EXE="
set "VENV_LOCAL=%~dp0..\.venv_local\Scripts\python.exe"
set "VENV_DEFAULT=%~dp0..\.venv\Scripts\python.exe"

if exist "%VENV_LOCAL%" (
    "%VENV_LOCAL%" -c "import pip" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_EXE=%VENV_LOCAL%"
    )
)

if not defined PYTHON_EXE if exist "%VENV_DEFAULT%" (
    "%VENV_DEFAULT%" -c "import pip" >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_EXE=%VENV_DEFAULT%"
    )
)

if not defined PYTHON_EXE (
    set "PYTHON_EXE=python"
)

echo ========================================
echo   AI Lecturer unified startup
echo ========================================
echo Using Python: %PYTHON_EXE%
echo.
echo Tip: do not run `python ..\.venv_local\Scripts\python.exe`
echo Use this script, or run:
echo   "%PYTHON_EXE%" start_unified.py
echo.

"%PYTHON_EXE%" start_unified.py

pause

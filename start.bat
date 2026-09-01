@echo off
setlocal EnableExtensions

set "CHECK_ARG="
set "BROWSER_ARG="

if /I "%~1"=="--check" set "CHECK_ARG=-Check"
if /I "%~1"=="--no-browser" set "BROWSER_ARG=-NoBrowser"
if /I "%~2"=="--check" set "CHECK_ARG=-Check"
if /I "%~2"=="--no-browser" set "BROWSER_ARG=-NoBrowser"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev.ps1" %CHECK_ARG% %BROWSER_ARG%
exit /b %ERRORLEVEL%

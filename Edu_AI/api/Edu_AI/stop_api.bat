@echo off
REM 停止API服务脚本 (Windows)
chcp 65001 >nul
echo ========================================
echo    停止 RAG问答API 服务
echo ========================================
echo.

set PORT=8000

echo 正在查找占用端口 %PORT% 的进程...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 未发现占用端口 %PORT% 的进程
    pause
    exit /b 0
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    set PID=%%a
    echo 找到进程 ID: !PID!
    echo 正在停止进程...
    taskkill /F /PID !PID!
    if !ERRORLEVEL! EQU 0 (
        echo 服务已成功停止
    ) else (
        echo 停止失败，可能需要管理员权限
        echo 请以管理员身份运行此脚本
    )
)

echo.
pause


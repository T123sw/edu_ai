@echo off
REM RAG问答API启动脚本 (Windows)
chcp 65001 >nul
echo ========================================
echo    RAG问答API服务启动脚本
echo ========================================
echo.

REM 设置工作目录为当前脚本所在目录，确保相对路径稳定
cd /d %~dp0

REM 优先使用项目本地虚拟环境，避免误用全局 Anaconda / uvicorn
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    echo 检测到本地虚拟环境: %PYTHON_EXE%
) else (
    echo 未检测到本地虚拟环境，回退到系统 Python
    set "PYTHON_EXE=python"
)
echo.

REM 设置端口号
set PORT=8001

REM 检查端口是否被占用
echo [1/3] 检查端口 %PORT% 占用情况...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 警告: 端口 %PORT% 已被占用，正在尝试停止占用进程...
    
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
        echo 发现进程 ID: %%a
        echo 正在停止进程...
        taskkill /F /PID %%a >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            echo 进程已停止
            timeout /t 2 /nobreak >nul
        ) else (
            echo 无法停止进程（可能需要管理员权限），尝试使用端口 8001...
            set PORT=8001
        )
    )
) else (
    echo 端口 %PORT% 可用
)
echo.

REM 检查是否安装了uvicorn
echo [2/3] 检查依赖...
%PYTHON_EXE% -c "import uvicorn" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 未找到uvicorn，尝试安装...
    %PYTHON_EXE% -m pip install uvicorn fastapi
)
echo.

REM 启动服务
echo [3/3] 启动服务...
echo ========================================
echo API服务将运行在: http://localhost:%PORT%
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

setlocal enabledelayedexpansion
%PYTHON_EXE% -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

pause

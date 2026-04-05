@echo off
chcp 65001 >nul
echo ========================================
echo 启动简化对话后端服务
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.12+
    pause
    exit /b 1
)

echo.
echo [2/2] 启动简化对话服务...
echo API服务将运行在: http://localhost:8000
echo 按Ctrl+C 停止服务
echo.

python -m uvicorn app.simple_chat:app --host 0.0.0.0 --port 8000 --reload

pause


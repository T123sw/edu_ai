@echo off
echo ========================================
echo    Edu-AI 本地启动脚本
echo ========================================
echo.

echo [1/2] 启动后端服务...
cd api/src
start "Edu-AI Backend" cmd /k "start_api.bat"

echo [2/2] 等待3秒后启动前端...
timeout /t 3 /nobreak >nul

cd ../..
echo 启动前端开发服务器...
start "Edu-AI Frontend" cmd /k "npm run dev"

ollama serve

echo.
echo ========================================
echo 服务启动完成！
echo 前端地址: http://localhost:5173
echo 后端地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键关闭此窗口...
pause >nul
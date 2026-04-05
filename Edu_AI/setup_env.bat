@echo off
REM Edu-AI 环境安装脚本 (Windows)

echo ==========================================
echo Edu-AI 环境安装脚本
echo ==========================================
echo.

REM 检查 Conda 是否安装
where conda >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 Conda，请先安装 Miniconda 或 Anaconda
    echo 下载地址: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo [OK] 检测到 Conda
conda --version
echo.

REM 检查是否在项目根目录
if not exist "environment.yml" (
    echo [错误] 未找到 environment.yml，请确保在 Edu_AI 目录下运行此脚本
    pause
    exit /b 1
)

REM 步骤 1: 创建 Conda 环境
echo [1/4] 创建 Conda 环境...
conda env list | findstr /C:"edu-ai " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 环境 'edu-ai' 已存在，是否覆盖？(Y/N)
    set /p response=
    if /i "%response%"=="Y" (
        conda env remove -n edu-ai -y
        conda env create -f environment.yml
    ) else (
        echo 跳过环境创建，使用现有环境
    )
) else (
    conda env create -f environment.yml
)

if %ERRORLEVEL% NEQ 0 (
    echo [错误] Conda 环境创建失败
    pause
    exit /b 1
)

echo [OK] Conda 环境创建完成
echo.

REM 激活环境
echo [2/4] 激活环境并验证...
call conda activate edu-ai

REM 验证 Python
python --version
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Python 验证失败
    pause
    exit /b 1
)

echo [OK] Python 环境正常

REM 验证 Node.js
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [警告] Node.js 未找到，将通过 conda 安装
    conda install nodejs=20 -c conda-forge -y
)

node --version
echo [OK] Node.js 环境正常
echo.

REM 步骤 3: 安装后端依赖
echo [3/4] 检查后端依赖...
if exist "api\Edu_AI\requirements_api.txt" (
    echo 安装后端 Python 依赖...
    cd api\Edu_AI
    pip install -r requirements_api.txt
    cd ..\..
    if %ERRORLEVEL% NEQ 0 (
        echo [警告] 后端依赖安装可能存在问题，请手动检查
    ) else (
        echo [OK] 后端依赖安装完成
    )
) else (
    echo [警告] 未找到 requirements_api.txt，跳过后端依赖安装
)
echo.

REM 步骤 4: 安装前端依赖
echo [4/4] 安装前端 Node.js 依赖...
if exist "package.json" (
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
    echo [OK] 前端依赖安装完成
) else (
    echo [错误] 未找到 package.json
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [完成] 环境安装完成！
echo ==========================================
echo.
echo 下一步：
echo 1. 激活环境: conda activate edu-ai
echo 2. 配置 .env 文件（参考 ENVIRONMENT.md）
echo 3. 启动后端: cd api ^&^& uvicorn Edu_AI.app.main:app --host 0.0.0.0 --port 8001 --reload
echo 4. 启动前端: npm run dev
echo.
pause


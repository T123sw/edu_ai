# EduAgent 依赖安装脚本
Write-Host "正在安装 EduAgent 依赖..." -ForegroundColor Green

# 检查虚拟环境
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "检测到虚拟环境，使用虚拟环境 Python" -ForegroundColor Yellow
    $python = ".venv\Scripts\python.exe"
} else {
    Write-Host "使用系统 Python" -ForegroundColor Yellow
    $python = "python"
}

# 安装依赖
Write-Host "`n安装核心依赖..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install jinja2 langchain-core langchain-deepseek langgraph langchain-openai

Write-Host "`n安装 Web 框架..." -ForegroundColor Cyan
& $python -m pip install fastapi uvicorn[standard]

Write-Host "`n安装文档处理库..." -ForegroundColor Cyan
& $python -m pip install pymupdf python-pptx

Write-Host "`n安装网络请求库..." -ForegroundColor Cyan
& $python -m pip install requests beautifulsoup4 lxml

Write-Host "`n安装网页处理库..." -ForegroundColor Cyan
& $python -m pip install playwright readabilipy markdownify

Write-Host "`n安装其他工具..." -ForegroundColor Cyan
& $python -m pip install pydantic

Write-Host "`n安装 Playwright 浏览器..." -ForegroundColor Cyan
& $python -m playwright install chromium

Write-Host "`n✅ 依赖安装完成！" -ForegroundColor Green
Write-Host "`n运行测试: python test_config.py" -ForegroundColor Yellow


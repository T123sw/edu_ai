# 快速修复脚本

Write-Host "=" -NoNewline
Write-Host ("=" * 59)
Write-Host "快速修复问题"
Write-Host ("=" * 60)
Write-Host ""

# 1. 关闭占用端口的进程
Write-Host "步骤1: 检查并关闭占用端口8848的进程..." -ForegroundColor Cyan
$portInfo = netstat -ano | findstr :8848
if ($portInfo) {
    $pid = ($portInfo -split '\s+')[-1]
    Write-Host "发现进程ID: $pid" -ForegroundColor Yellow
    $confirm = Read-Host "是否关闭此进程? (Y/N)"
    if ($confirm -eq 'Y' -or $confirm -eq 'y') {
        taskkill /F /PID $pid
        Write-Host "进程已关闭" -ForegroundColor Green
        Start-Sleep -Seconds 2
    } else {
        Write-Host "跳过关闭进程" -ForegroundColor Yellow
    }
} else {
    Write-Host "端口8848未被占用" -ForegroundColor Green
}

Write-Host ""

# 2. 验证爬虫模块路径
Write-Host "步骤2: 验证爬虫模块路径..." -ForegroundColor Cyan
$crawleUrlPath = "D:\Edu_AI_1\自动化爬虫\src\selenium_way\crawle_url.py"
if (Test-Path $crawleUrlPath) {
    Write-Host "✓ 爬虫模块文件存在" -ForegroundColor Green
} else {
    Write-Host "✗ 爬虫模块文件不存在: $crawleUrlPath" -ForegroundColor Red
}

Write-Host ""

# 3. 测试导入
Write-Host "步骤3: 测试Python导入..." -ForegroundColor Cyan
cd D:\Edu_AI_1\EduAgent
python -c "from services.crawler_service import get_crawler_service; print('导入成功')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 导入测试成功" -ForegroundColor Green
} else {
    Write-Host "✗ 导入测试失败" -ForegroundColor Red
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "修复完成! 现在可以尝试启动服务:" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor White
Write-Host ("=" * 60)


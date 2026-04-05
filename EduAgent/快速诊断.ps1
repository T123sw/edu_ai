# 快速诊断脚本

Write-Host "=" -NoNewline
Write-Host ("=" * 59)
Write-Host "深度搜索超时问题诊断"
Write-Host ("=" * 60)
Write-Host ""

# 1. 检查服务是否运行
Write-Host "步骤1: 检查API服务状态..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8848/" -TimeoutSec 5 -UseBasicParsing
    Write-Host "✅ API服务正在运行" -ForegroundColor Green
} catch {
    Write-Host "❌ API服务未运行或无法访问" -ForegroundColor Red
    Write-Host "   请先启动服务: python main.py" -ForegroundColor Yellow
    exit
}

Write-Host ""

# 2. 测试简单的深度搜索API
Write-Host "步骤2: 测试深度搜索API（超时180秒）..." -ForegroundColor Cyan
Write-Host "⏳ 这可能需要几分钟，请耐心等待..." -ForegroundColor Yellow
Write-Host ""

try {
    $body = @{
        query = "测试"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8848/agent/deepsearch" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 180
    
    if ($response.ok) {
        Write-Host "✅ 深度搜索API正常!" -ForegroundColor Green
        Write-Host "找到 $($response.results.Count) 个URL"
    } else {
        Write-Host "❌ 深度搜索API返回错误" -ForegroundColor Red
        Write-Host "错误: $($response.message)"
    }
} catch {
    if ($_.Exception.Response.StatusCode -eq 504 -or $_.Exception.Message -like "*timeout*") {
        Write-Host "❌ 请求超时!" -ForegroundColor Red
        Write-Host "   深度搜索执行时间过长，建议:" -ForegroundColor Yellow
        Write-Host "   1. 直接测试深度搜索函数: python test_deepsearch_direct.py" -ForegroundColor White
        Write-Host "   2. 检查服务端日志查看卡在哪里" -ForegroundColor White
        Write-Host "   3. 减少递归限制或优化Agent流程" -ForegroundColor White
    } else {
        Write-Host "❌ 发生错误: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "诊断完成!"
Write-Host ("=" * 60)
Write-Host ""
Write-Host "建议下一步:" -ForegroundColor Cyan
Write-Host "  1. 运行: python test_deepsearch_direct.py" -ForegroundColor White
Write-Host "  2. 查看服务端日志" -ForegroundColor White
Write-Host "  3. 检查LLM配置和网络连接" -ForegroundColor White


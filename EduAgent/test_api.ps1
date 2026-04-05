# PowerShell脚本：测试深度搜索并爬取API

# 配置
$apiUrl = "http://127.0.0.1:8848/agent/deepsearch-and-crawl"
$query = "计算思维 课程大纲 PDF"
$maxUrls = 3

Write-Host "=" -NoNewline
Write-Host ("=" * 59)
Write-Host "测试深度搜索并爬取API"
Write-Host ("=" * 60)
Write-Host ""

# 构建请求体
$body = @{
    query = $query
    max_urls = $maxUrls
    crawl_timeout = 30
} | ConvertTo-Json

Write-Host "请求URL: $apiUrl"
Write-Host "查询: $query"
Write-Host "最多爬取URL数: $maxUrls"
Write-Host ""
Write-Host ("-" * 60)
Write-Host ""

try {
    # 发送POST请求
    $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300
    
    Write-Host "✅ 请求成功!" -ForegroundColor Green
    Write-Host ""
    Write-Host "批次ID: $($response.batch_id)"
    Write-Host "搜索到URL数: $($response.search_results.total_urls)"
    Write-Host "爬取成功: $($response.crawl_results.success_count)"
    Write-Host "爬取失败: $($response.crawl_results.failed_count)"
    Write-Host ""
    
    # 显示结果
    if ($response.crawl_results.results) {
        Write-Host "前3个结果:" -ForegroundColor Yellow
        $count = 0
        foreach ($item in $response.crawl_results.results) {
            $count++
            if ($count -gt 3) { break }
            
            Write-Host ""
            Write-Host "$count. URL: $($item.url)" -ForegroundColor Cyan
            Write-Host "   标题: $($item.title)"
            Write-Host "   状态: $($item.status)"
            Write-Host "   内容类型: $($item.content_type)"
            if ($item.content) {
                $preview = $item.content.Substring(0, [Math]::Min(100, $item.content.Length))
                Write-Host "   内容预览: $preview..."
            }
        }
    }
    
    # 如果成功，获取详细结果
    if ($response.ok -and $response.batch_id) {
        Write-Host ""
        Write-Host ("-" * 60)
        Write-Host "获取详细结果..." -ForegroundColor Yellow
        
        $detailUrl = "http://127.0.0.1:8848/agent/crawl-results/$($response.batch_id)"
        $detailResponse = Invoke-RestMethod -Uri $detailUrl -Method Get -TimeoutSec 30
        
        Write-Host "✅ 获取成功!" -ForegroundColor Green
        Write-Host "查询: $($detailResponse.query)"
        Write-Host "总URL数: $($detailResponse.total_urls)"
        Write-Host "成功: $($detailResponse.success_count)"
        Write-Host "失败: $($detailResponse.failed_count)"
    }
    
} catch {
    Write-Host "❌ 请求失败!" -ForegroundColor Red
    Write-Host "错误信息: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "提示: 请确保FastAPI服务已启动 (python main.py)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "测试完成!"
Write-Host ("=" * 60)


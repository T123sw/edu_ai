"""
完整功能测试：深度搜索 + 爬取 + 内容清洗
支持长时间运行，超时时间已延长
"""
import requests
import json
import time
import sys
from typing import Optional, Dict, Any


def test_deepsearch_and_crawl(
    query: str,
    max_urls: int = 5,
    crawl_timeout: int = 30,
    api_timeout: int = 1800  # 30分钟超时
) -> Optional[Dict[str, Any]]:
    """
    测试完整的深度搜索并爬取流程
    
    Args:
        query: 搜索查询
        max_urls: 最多爬取的URL数量
        crawl_timeout: 单个URL爬取超时（秒）
        api_timeout: API请求总超时（秒，默认30分钟）
    
    Returns:
        API响应结果
    """
    url = "http://127.0.0.1:8848/agent/deepsearch-and-crawl"
    
    payload = {
        "query": query,
        "max_urls": max_urls,
        "crawl_timeout": crawl_timeout
    }
    
    print("=" * 70)
    print("完整功能测试：深度搜索 + 爬取 + 内容清洗")
    print("=" * 70)
    print(f"查询: {query}")
    print(f"最多爬取URL数: {max_urls}")
    print(f"单个URL爬取超时: {crawl_timeout}秒")
    print(f"API总超时: {api_timeout}秒（{api_timeout//60}分钟）")
    print(f"请求URL: {url}")
    print("-" * 70)
    print("⏳ 请求已发送，正在处理中...")
    print("   预计耗时:")
    print(f"   - 深度搜索: ~1-3分钟")
    print(f"   - 爬取URL: 每个URL ~{crawl_timeout}秒")
    print(f"   - 总预计: ~{1 + max_urls * crawl_timeout // 60}分钟")
    print("   请耐心等待...\n")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url, 
            json=payload, 
            timeout=api_timeout  # 30分钟超时
        )
        
        elapsed = time.time() - start_time
        result = response.json()
        
        print(f"✅ 请求完成! 总耗时: {elapsed:.2f}秒 ({elapsed/60:.2f}分钟)")
        print(f"状态码: {response.status_code}")
        print("-" * 70)
        
        if result.get("ok"):
            print("\n📊 结果统计:")
            print(f"  批次ID: {result.get('batch_id')}")
            print(f"  搜索到URL数: {result.get('search_results', {}).get('total_urls', 0)}")
            
            crawl_results = result.get('crawl_results', {})
            print(f"  爬取总数: {crawl_results.get('total_urls', 0)}")
            print(f"  爬取成功: {crawl_results.get('success_count', 0)}")
            print(f"  爬取失败: {crawl_results.get('failed_count', 0)}")
            
            # 显示详细结果
            results = crawl_results.get('results', [])
            if results:
                print(f"\n📋 详细结果 ({len(results)} 个):")
                for i, item in enumerate(results, 1):
                    status_icon = "✅" if item.get('status') == 'success' else "❌"
                    print(f"\n  {i}. {status_icon} {item.get('url', 'N/A')}")
                    print(f"     标题: {item.get('title', 'N/A')}")
                    print(f"     类型: {item.get('content_type', 'N/A')}")
                    print(f"     状态: {item.get('status', 'N/A')}")
                    if item.get('error_message'):
                        print(f"     错误: {item.get('error_message')}")
                    if item.get('content'):
                        content_preview = item['content'][:150].replace('\n', ' ')
                        print(f"     内容预览: {content_preview}...")
            
            # 保存结果到文件
            output_file = f"deepsearch_crawl_result_{int(time.time())}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存到: {output_file}")
            
        else:
            print("\n❌ 请求失败!")
            print(f"错误信息: {result.get('message', '未知错误')}")
        
        return result
    
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"\n❌ 请求超时! 已运行: {elapsed:.2f}秒 ({elapsed/60:.2f}分钟)")
        print(f"   超时设置: {api_timeout}秒 ({api_timeout//60}分钟)")
        print("   建议:")
        print("   1. 减少max_urls数量")
        print("   2. 减少crawl_timeout时间")
        print("   3. 检查网络连接")
        return None
    
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接失败! 请确保FastAPI服务已启动")
        print("   启动命令: python main.py")
        return None
    
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 发生错误: {type(e).__name__}: {e}")
        print(f"   已运行: {elapsed:.2f}秒")
        return None


def get_crawl_results(batch_id: str) -> Optional[Dict[str, Any]]:
    """获取爬取结果详情"""
    url = f"http://127.0.0.1:8848/agent/crawl-results/{batch_id}"
    
    print(f"\n📥 获取详细结果...")
    print(f"批次ID: {batch_id}")
    
    try:
        response = requests.get(url, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            print("✅ 获取成功!")
            return result
        else:
            print("❌ 获取失败!")
            print(f"错误: {result.get('message')}")
            return None
    
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='测试深度搜索并爬取功能')
    parser.add_argument('query', nargs='?', default='计算思维 课程大纲 PDF', help='搜索查询')
    parser.add_argument('--max-urls', type=int, default=5, help='最多爬取的URL数量（默认5）')
    parser.add_argument('--crawl-timeout', type=int, default=30, help='单个URL爬取超时（秒，默认30）')
    parser.add_argument('--api-timeout', type=int, default=1800, help='API总超时（秒，默认1800=30分钟）')
    
    args = parser.parse_args()
    
    # 执行测试
    result = test_deepsearch_and_crawl(
        query=args.query,
        max_urls=args.max_urls,
        crawl_timeout=args.crawl_timeout,
        api_timeout=args.api_timeout
    )
    
    # 如果成功，获取详细结果
    if result and result.get("ok") and result.get("batch_id"):
        batch_id = result["batch_id"]
        detail = get_crawl_results(batch_id)
        
        if detail:
            print("\n" + "=" * 70)
            print("完整结果已获取!")
            print("=" * 70)
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)


"""
测试深度搜索并爬取功能
"""
import requests
import json
from typing import Dict, Any


def test_deepsearch_and_crawl(query: str, max_urls: int = 5) -> Dict[str, Any]:
    """
    测试深度搜索并爬取API
    
    Args:
        query: 搜索查询
        max_urls: 最多爬取的URL数量
    
    Returns:
        API响应结果
    """
    url = "http://127.0.0.1:8848/agent/deepsearch-and-crawl"
    
    payload = {
        "query": query,
        "max_urls": max_urls,
        "crawl_timeout": 30
    }
    
    print(f"正在测试深度搜索并爬取...")
    print(f"查询: {query}")
    print(f"最多爬取URL数: {max_urls}")
    print(f"请求URL: {url}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print("-" * 60)
    
    try:
        print("⏳ 请求已发送，正在处理中（这可能需要几分钟）...")
        print("   - 深度搜索: ~1-2分钟")
        print("   - 爬取URL: 每个URL ~10-30秒")
        print("   - 请耐心等待...\n")
        
        response = requests.post(url, json=payload, timeout=600)  # 10分钟超时
        result = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)[:2000]}...")
        
        if result.get("ok"):
            print("\n✅ 请求成功!")
            print(f"批次ID: {result.get('batch_id')}")
            print(f"搜索到URL数: {result.get('search_results', {}).get('total_urls', 0)}")
            print(f"爬取成功: {result.get('crawl_results', {}).get('success_count', 0)}")
            print(f"爬取失败: {result.get('crawl_results', {}).get('failed_count', 0)}")
            
            # 显示前3个结果
            results = result.get('crawl_results', {}).get('results', [])
            if results:
                print("\n前3个结果:")
                for i, item in enumerate(results[:3], 1):
                    print(f"\n{i}. URL: {item.get('url', 'N/A')}")
                    print(f"   标题: {item.get('title', 'N/A')}")
                    print(f"   状态: {item.get('status', 'N/A')}")
                    print(f"   内容类型: {item.get('content_type', 'N/A')}")
                    if item.get('content'):
                        content_preview = item['content'][:100].replace('\n', ' ')
                        print(f"   内容预览: {content_preview}...")
        else:
            print("\n❌ 请求失败!")
            print(f"错误信息: {result.get('message', '未知错误')}")
        
        return result
    
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败! 请确保FastAPI服务已启动 (python main.py)")
        return None
    except requests.exceptions.Timeout:
        print("❌ 请求超时! 爬取过程可能较长，请稍后重试")
        return None
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return None


def test_get_crawl_results(batch_id: str) -> Dict[str, Any]:
    """获取爬取结果详情"""
    url = f"http://127.0.0.1:8848/agent/crawl-results/{batch_id}"
    
    print(f"\n正在获取爬取结果详情...")
    print(f"批次ID: {batch_id}")
    print(f"请求URL: {url}")
    print("-" * 60)
    
    try:
        response = requests.get(url, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            print("✅ 获取成功!")
            print(f"查询: {result.get('query')}")
            print(f"总URL数: {result.get('total_urls')}")
            print(f"成功: {result.get('success_count')}")
            print(f"失败: {result.get('failed_count')}")
            
            results = result.get('results', [])
            print(f"\n详细结果 ({len(results)} 个):")
            for i, item in enumerate(results, 1):
                print(f"\n{i}. {item.get('url')}")
                print(f"   标题: {item.get('title', 'N/A')}")
                print(f"   状态: {item.get('status')}")
                if item.get('error_message'):
                    print(f"   错误: {item.get('error_message')}")
        else:
            print("❌ 获取失败!")
            print(f"错误: {result.get('message')}")
        
        return result
    
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return None


def test_get_crawl_history(limit: int = 5) -> Dict[str, Any]:
    """获取爬取历史"""
    url = f"http://127.0.0.1:8848/agent/crawl-history?limit={limit}"
    
    print(f"\n正在获取爬取历史...")
    print(f"请求URL: {url}")
    print("-" * 60)
    
    try:
        response = requests.get(url, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            batches = result.get('batches', [])
            print(f"✅ 获取成功! 共 {len(batches)} 个批次")
            
            for i, batch in enumerate(batches, 1):
                print(f"\n{i}. 批次ID: {batch.get('batch_id')}")
                print(f"   查询: {batch.get('query')}")
                print(f"   总URL数: {batch.get('total_urls')}")
                print(f"   成功: {batch.get('success_count')}")
                print(f"   失败: {batch.get('failed_count')}")
                print(f"   创建时间: {batch.get('created_at')}")
        else:
            print("❌ 获取失败!")
        
        return result
    
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("深度搜索并爬取功能测试")
    print("=" * 60)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        query = sys.argv[1]
        max_urls = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    else:
        query = "计算思维 课程大纲 PDF"
        max_urls = 3  # 测试时用较小的数量
    
    # 测试1: 深度搜索并爬取
    result = test_deepsearch_and_crawl(query, max_urls)
    
    # 如果成功，测试获取结果详情
    if result and result.get("ok") and result.get("batch_id"):
        batch_id = result["batch_id"]
        test_get_crawl_results(batch_id)
    
    # 测试获取历史
    test_get_crawl_history(limit=5)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


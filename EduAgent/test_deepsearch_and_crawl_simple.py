"""
简化版测试脚本 - 只测试深度搜索，不爬取
用于快速验证深度搜索功能
"""
import requests
import json


def test_deepsearch_only(query: str):
    """只测试深度搜索，不爬取"""
    url = "http://127.0.0.1:8848/agent/deepsearch"
    
    print(f"测试深度搜索（不爬取）...")
    print(f"查询: {query}")
    print("-" * 60)
    
    try:
        response = requests.post(url, params={"query": query}, timeout=180)
        result = response.json()
        
        if result.get("ok"):
            print("✅ 深度搜索成功!")
            print(f"找到 {len(result.get('results', []))} 个URL")
            print("\n前5个URL:")
            for i, url in enumerate(result.get('results', [])[:5], 1):
                print(f"  {i}. {url}")
        else:
            print("❌ 深度搜索失败!")
            print(f"错误: {result.get('message')}")
        
        return result
    
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return None


if __name__ == "__main__":
    query = "计算思维 课程大纲 PDF"
    test_deepsearch_only(query)


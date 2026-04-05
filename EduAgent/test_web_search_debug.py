"""测试 web_search 工具的实际返回结果"""
import json
from tools.search.websearch import web_search

def test_web_search():
    query = "计算思维 课程大纲 PDF"
    print(f"测试查询: {query}")
    print("=" * 60)
    
    # 直接调用工具
    result = web_search.invoke({
        "query": query,
        "top_k": 8,
        "language": "zh-CN"
    })
    
    print(f"\n返回结果类型: {type(result)}")
    print(f"结果数量: {len(result) if isinstance(result, list) else 'N/A'}")
    print("\n前3条结果:")
    for i, item in enumerate(result[:3] if isinstance(result, list) else [], 1):
        print(f"\n{i}. {json.dumps(item, ensure_ascii=False, indent=2)}")
    
    # 检查格式
    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        print(f"\n第一条结果的键: {list(first.keys()) if isinstance(first, dict) else 'N/A'}")
        if isinstance(first, dict):
            print(f"  - title: {first.get('title', 'N/A')[:50]}")
            print(f"  - url: {first.get('url', 'N/A')[:80]}")
            print(f"  - snippet: {first.get('snippet', 'N/A')[:50] if first.get('snippet') else 'N/A'}")

if __name__ == "__main__":
    test_web_search()


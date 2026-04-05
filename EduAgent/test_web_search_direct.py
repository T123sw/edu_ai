"""直接测试 web_search 工具，检查返回结果质量"""
import json
from tools.search.websearch import web_search, search

def test_search_direct():
    """直接测试底层 search 函数"""
    print("=" * 60)
    print("测试 1: 直接调用 search() 函数")
    print("=" * 60)
    
    query = "计算思维 课程大纲 PDF"
    print(f"\n查询: {query}")
    
    try:
        results = search(
            query=query,
            top_k=5,
            endpoint="http://localhost:8090/search",
            language="zh-CN",
            timeout=12,
        )
        print(f"\n返回 {len(results)} 条结果:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. 标题: {r.get('title', '')[:60]}")
            print(f"   URL: {r.get('url', '')[:80]}")
            print(f"   摘要: {r.get('snippet', '')[:100]}")
            print(f"   引擎: {r.get('engine', '')}")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")

def test_web_search_tool():
    """测试 LangChain tool 包装的 web_search"""
    print("\n" + "=" * 60)
    print("测试 2: 调用 web_search LangChain tool")
    print("=" * 60)
    
    query = "计算思维 课程大纲 PDF"
    print(f"\n查询: {query}")
    
    try:
        # 直接调用 tool 的 invoke 方法
        result = web_search.invoke({
            "query": query,
            "top_k": 5,
            "language": "zh-CN"
        })
        print(f"\n返回 {len(result)} 条结果:")
        for i, r in enumerate(result, 1):
            if isinstance(r, dict):
                print(f"\n{i}. 标题: {r.get('title', '')[:60]}")
                print(f"   URL: {r.get('url', '')[:80]}")
                print(f"   摘要: {r.get('snippet', '')[:100]}")
            else:
                print(f"{i}. {r}")
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

def test_multiple_queries():
    """测试多个不同的查询，看搜索结果质量"""
    print("\n" + "=" * 60)
    print("测试 3: 测试多个查询变体")
    print("=" * 60)
    
    queries = [
        "计算思维 课程大纲 PDF",
        "计算思维 教学大纲",
        "computational thinking syllabus PDF",
        "计算思维 课程 大纲 文件",
    ]
    
    for query in queries:
        print(f"\n--- 查询: {query} ---")
        try:
            results = search(
                query=query,
                top_k=3,
                endpoint="http://localhost:8090/search",
                language="zh-CN",
                timeout=10,
            )
            print(f"返回 {len(results)} 条结果")
            for i, r in enumerate(results[:2], 1):  # 只显示前2条
                print(f"  {i}. {r.get('title', '')[:50]} | {r.get('url', '')[:50]}")
        except Exception as e:
            print(f"  ❌ 错误: {type(e).__name__}")

if __name__ == "__main__":
    test_search_direct()
    test_web_search_tool()
    test_multiple_queries()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


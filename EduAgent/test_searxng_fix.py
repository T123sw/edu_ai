"""
测试SearxNG修复是否成功
"""
from tools.search.websearch import search_links
import time

print("=" * 60)
print("测试SearxNG修复")
print("=" * 60)

print("\n测试web_search工具...")
print("查询: 'test'")
print("期望结果数: 3")
print("-" * 60)

start = time.time()
try:
    results = search_links('test', top_k=3)
    elapsed = time.time() - start
    
    print(f"\n✅ 测试完成!")
    print(f"耗时: {elapsed:.2f}秒")
    print(f"结果数: {len(results)}")
    
    if results:
        print("\n前3个结果:")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r.get('url', 'N/A')}")
            print(f"     标题: {r.get('title', 'N/A')}")
            print(f"     引擎: {r.get('engine', 'N/A')}")
        
        if elapsed < 3:
            print(f"\n✅ 性能良好! (耗时 {elapsed:.2f}秒 < 3秒)")
            print("   SearxNG修复成功，使用API方式")
        else:
            print(f"\n⚠️  性能较慢 (耗时 {elapsed:.2f}秒 >= 3秒)")
            print("   可能仍在使用HTML解析方式")
    else:
        print("\n❌ 未返回结果")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ 发生错误: {type(e).__name__}: {e}")
    print(f"耗时: {elapsed:.2f}秒")

print("\n" + "=" * 60)


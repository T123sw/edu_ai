"""
测试web_search修复是否成功
"""
import sys
import time
from tools.search.websearch import search_links

print("=" * 60)
print("测试web_search修复")
print("=" * 60)

print("\n测试查询: 'test'")
print("期望结果数: 3")
print("-" * 60)

start = time.time()
try:
    results = search_links('test', top_k=3)
    elapsed = time.time() - start
    
    print(f"\n[OK] 测试完成!")
    print(f"耗时: {elapsed:.2f}秒")
    print(f"结果数: {len(results)}")
    
    if results:
        print("\n前3个URL:")
        for i, url in enumerate(results[:3], 1):
            print(f"  {i}. {url[:80]}")
        
        if elapsed < 3:
            print(f"\n[OK] 性能良好! (耗时 {elapsed:.2f}秒 < 3秒)")
            print("   SearxNG修复成功，使用API方式")
        else:
            print(f"\n[WARNING] 性能较慢 (耗时 {elapsed:.2f}秒 >= 3秒)")
            print("   可能仍在使用HTML解析方式")
    else:
        print("\n[ERROR] 未返回结果")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"\n[ERROR] 发生错误: {type(e).__name__}: {e}")
    print(f"耗时: {elapsed:.2f}秒")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)


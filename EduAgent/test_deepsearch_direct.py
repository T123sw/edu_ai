"""
直接测试深度搜索函数（不通过API）
用于诊断深度搜索是否正常工作
"""
import sys
from pathlib import Path

# 确保在正确的目录
sys.path.insert(0, str(Path(__file__).parent))

from deepsearch import deepsearch_large_llm
import time

def test_deepsearch_direct():
    """直接测试深度搜索函数"""
    query = "计算思维 课程大纲 PDF"
    
    print("=" * 60)
    print("直接测试深度搜索函数")
    print("=" * 60)
    print(f"查询: {query}")
    print("-" * 60)
    print("⏳ 开始深度搜索（这可能需要1-3分钟）...")
    print("")
    
    start_time = time.time()
    
    try:
        result = deepsearch_large_llm(query)
        
        elapsed = time.time() - start_time
        
        if result:
            print(f"✅ 深度搜索成功! 耗时: {elapsed:.2f}秒")
            print(f"找到 {len(result.get('links', []))} 个链接:")
            for i, link in enumerate(result.get('links', [])[:5], 1):
                print(f"  {i}. {link}")
        else:
            print(f"❌ 深度搜索返回None，耗时: {elapsed:.2f}秒")
            print("可能的原因:")
            print("  - Agent执行超时")
            print("  - 结构化输出失败")
            print("  - 网络问题")
        
        return result
    
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n⚠️ 用户中断，已运行: {elapsed:.2f}秒")
        return None
    
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 发生错误: {type(e).__name__}: {e}")
        print(f"耗时: {elapsed:.2f}秒")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_deepsearch_direct()
    
    if result:
        print("\n" + "=" * 60)
        print("测试完成! 深度搜索功能正常")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("测试失败! 请检查:")
        print("  1. LLM配置是否正确")
        print("  2. 网络连接是否正常")
        print("  3. 查看服务端日志")
        print("=" * 60)


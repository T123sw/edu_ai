"""诊断搜索工具问题"""
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

def test_ddg_direct():
    """直接测试 DuckDuckGo HTML 搜索"""
    query = "计算思维 课程大纲 PDF"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    
    print(f"测试 DuckDuckGo: {url}")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentSearch/1.0)"}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"状态码: {r.status_code}")
        
        soup = BeautifulSoup(r.text, "lxml")
        
        # 检查各种可能的选择器
        selectors = [
            ".result",
            ".web-result", 
            "div.result",
            "a.result__a",
            ".result-link"
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            print(f"\n选择器 '{selector}': 找到 {len(items)} 个元素")
            if items:
                print(f"  第一个元素的类名: {items[0].get('class', [])}")
                print(f"  第一个元素的标签: {items[0].name}")
                if items[0].select_one("a"):
                    a = items[0].select_one("a")
                    print(f"  第一个链接: {a.get('href', '')[:80]}")
                    print(f"  第一个标题: {a.get_text(strip=True)[:50]}")
                break
        
        # 保存 HTML 用于调试
        with open("ddg_debug.html", "w", encoding="utf-8") as f:
            f.write(r.text[:5000])  # 只保存前5000字符
        print("\n已保存 HTML 到 ddg_debug.html (前5000字符)")
        
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_ddg_direct()


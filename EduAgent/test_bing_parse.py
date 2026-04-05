"""测试 Bing HTML 解析，找出正确的选择器"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

def test_bing_html_structure():
    """测试 Bing 搜索页面的实际 HTML 结构"""
    query = "计算思维 课程大纲 PDF"
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print(f"请求 URL: {url}")
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    
    soup = BeautifulSoup(r.text, "lxml")
    
    # 测试不同的选择器
    selectors = [
        "li.b_algo",
        "li[class*='b_algo']",
        ".b_algo",
        "#b_results > li",
        "ol#b_results > li",
    ]
    
    for selector in selectors:
        items = soup.select(selector)
        print(f"\n选择器 '{selector}': 找到 {len(items)} 个元素")
        if items:
            first = items[0]
            # 尝试找标题和链接
            title_el = first.select_one("h2 a") or first.select_one("a")
            if title_el:
                print(f"  第一个结果标题: {title_el.get_text(strip=True)[:60]}")
                print(f"  第一个结果链接: {title_el.get('href', '')[:80]}")
            else:
                print(f"  未找到标题元素")
                # 打印前100个字符看看结构
                print(f"  元素内容预览: {str(first)[:200]}")
    
    # 保存 HTML 到文件供检查
    with open("bing_search_result.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("\n已保存 HTML 到 bing_search_result.html")

if __name__ == "__main__":
    test_bing_html_structure()


"""
调试Bing搜索结果，查看实际HTML结构
"""
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time

options = uc.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument('--headless=new')

driver = uc.Chrome(options=options, version_main=142)

try:
    url = 'https://www.bing.com/search?q=filetype%3apdf+计算思维&first=1'
    print(f"访问: {url}")
    driver.get(url)
    
    time.sleep(3)
    
    # 保存页面源码
    html = driver.page_source
    with open('bing_search_result.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("页面源码已保存到: bing_search_result.html")
    
    # 解析HTML
    soup = BeautifulSoup(html, 'lxml')
    container = soup.select_one('#b_results')
    
    if container:
        print(f"\n找到搜索结果容器，包含 {len(container.select('li'))} 个结果项")
        
        # 检查前3个链接的结构
        for i, part in enumerate(container.select('li')[:3], 1):
            links = part.select('h2 > a')
            for link in links:
                href = link.get('href')
                title = link.text.strip()[:50]
                print(f"\n结果 {i}:")
                print(f"  标题: {title}")
                print(f"  href: {href}")
                print(f"  所有属性: {link.attrs}")
    else:
        print("未找到搜索结果容器")
        print("页面标题:", driver.title)
        
finally:
    driver.quit()
    print("\n调试完成")


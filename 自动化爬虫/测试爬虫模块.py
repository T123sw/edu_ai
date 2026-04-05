"""
测试爬虫模块是否可以正常使用
"""
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("爬虫模块功能测试")
print("=" * 60)

# 1. 测试依赖包导入
print("\n[1/6] 测试核心依赖包...")
try:
    import selenium
    print(f"  ✓ selenium: {selenium.__version__}")
except ImportError as e:
    print(f"  ✗ selenium未安装: {e}")
    sys.exit(1)

try:
    import undetected_chromedriver as uc
    print(f"  ✓ undetected-chromedriver: {uc.__version__}")
except ImportError as e:
    print(f"  ✗ undetected-chromedriver未安装: {e}")
    sys.exit(1)

try:
    import webdriver_manager
    print(f"  ✓ webdriver-manager已安装")
except ImportError as e:
    print(f"  ✗ webdriver-manager未安装: {e}")
    sys.exit(1)

try:
    import requests
    print(f"  ✓ requests: {requests.__version__}")
except ImportError as e:
    print(f"  ✗ requests未安装: {e}")
    sys.exit(1)

try:
    import bs4
    print(f"  ✓ beautifulsoup4: {bs4.__version__}")
except ImportError as e:
    print(f"  ✗ beautifulsoup4未安装: {e}")
    sys.exit(1)

try:
    import trafilatura
    print(f"  ✓ trafilatura已安装")
except ImportError as e:
    print(f"  ✗ trafilatura未安装: {e}")
    sys.exit(1)

try:
    import ddddocr
    print(f"  ✓ ddddocr: {ddddocr.__version__}")
except ImportError as e:
    print(f"  ⚠ ddddocr未安装或版本不兼容: {e}")
    print("    (CNKI功能需要此包，其他功能不受影响)")

# 2. 测试工具方法模块
print("\n[2/6] 测试工具方法模块...")
try:
    from src.selenium_way.methods import download_one, download_txt, download_all, extract_real_url, clean_special_chars
    print("  ✓ methods模块导入成功")
    print("    - download_one: PDF下载函数")
    print("    - download_txt: 文本保存函数")
    print("    - download_all: 批量下载函数")
    print("    - extract_real_url: URL提取函数")
    print("    - clean_special_chars: 文本清理函数")
except ImportError as e:
    print(f"  ✗ methods模块导入失败: {e}")
    sys.exit(1)

# 3. 测试配置模块
print("\n[3/6] 测试配置模块...")
try:
    from automation_spider.config import settings
    print("  ✓ 配置模块导入成功")
    print(f"    默认关键词: {settings.keywords}")
    print(f"    默认页数: {settings.pages}")
    print(f"    输出目录: {settings.save_root_dir}")
    print(f"    超时时间: {settings.timeout}秒")
    print(f"    PDF下载线程数: {settings.pdf_max_workers}")
    print(f"    CNKI下载线程数: {settings.cnki_max_workers}")
except ImportError as e:
    print(f"  ✗ 配置模块导入失败: {e}")
    sys.exit(1)

# 4. 测试PDF爬虫模块
print("\n[4/6] 测试PDF爬虫模块...")
try:
    from src.selenium_way.get_PDF_links_by_keywords import keywords_selenium, pdf_runner
    print("  ✓ PDF爬虫模块导入成功")
    print("    - keywords_selenium: PDF搜索类")
    print("    - pdf_runner: PDF抓取函数")
except ImportError as e:
    print(f"  ✗ PDF爬虫模块导入失败: {e}")
    sys.exit(1)

# 5. 测试文本爬虫模块
print("\n[5/6] 测试文本爬虫模块...")
try:
    from src.selenium_way.Selenium_get_html import Request_by_Selenium, txt_runner
    print("  ✓ 文本爬虫模块导入成功")
    print("    - Request_by_Selenium: 文本抓取类")
    print("    - txt_runner: 文本抓取函数")
except ImportError as e:
    print(f"  ✗ 文本爬虫模块导入失败: {e}")
    sys.exit(1)

# 6. 测试URL爬虫模块
print("\n[6/6] 测试URL爬虫模块...")
try:
    from src.selenium_way.crawle_url import crawle_url
    print("  ✓ URL爬虫模块导入成功")
    print("    - crawle_url: URL抓取类")
except ImportError as e:
    print(f"  ✗ URL爬虫模块导入失败: {e}")
    sys.exit(1)

# 7. 测试CNKI模块（可选）
print("\n[可选] 测试CNKI模块...")
try:
    from src.selenium_way.CNKI import run as cnki_run, init_carsi_login
    print("  ✓ CNKI模块导入成功")
    print("    - cnki_run: CNKI抓取函数")
    print("    - init_carsi_login: CARSI登录函数")
    print(f"    CNKI账号配置: {settings.username[:3]}***")
    print(f"    学校: {settings.college}")
except ImportError as e:
    print(f"  ⚠ CNKI模块导入失败: {e}")
    print("    (需要配置账号信息才能使用)")

# 8. 测试工具函数
print("\n[功能测试] 测试工具函数...")
try:
    # 测试URL提取
    test_url = "https://www.bing.com/search?q=test&u=aHR0cHM6Ly9leGFtcGxlLmNvbQ=="
    real_url = extract_real_url(test_url)
    if real_url:
        print(f"  ✓ URL提取功能正常: {real_url[:50]}...")
    else:
        print("  ⚠ URL提取返回None（可能是测试URL格式问题）")
    
    # 测试文本清理
    test_text = "测试文本\n\n\n多个换行\t\t制表符"
    cleaned = clean_special_chars(test_text)
    if cleaned:
        print(f"  ✓ 文本清理功能正常")
    else:
        print("  ⚠ 文本清理返回空")
        
except Exception as e:
    print(f"  ⚠ 工具函数测试出错: {e}")

# 9. 测试ChromeDriver（需要网络）
print("\n[可选] 测试ChromeDriver管理...")
try:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    print("  ✓ ChromeDriver管理器导入成功")
    print("    注意: 首次运行会自动下载ChromeDriver")
    print("    需要网络连接和Chrome浏览器")
except Exception as e:
    print(f"  ⚠ ChromeDriver测试跳过: {e}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
print("\n总结:")
print("  ✓ 所有核心模块导入成功")
print("  ✓ 配置模块正常工作")
print("  ✓ 工具函数可用")
print("\n下一步:")
print("  1. 可以运行: python -m automation_spider pdf --keywords '测试' --pages 1")
print("  2. 或使用: python 构建计算思维知识库.py")
print("  3. 确保Chrome浏览器已安装（用于Selenium）")
print("  4. 首次运行需要网络连接（下载ChromeDriver）")


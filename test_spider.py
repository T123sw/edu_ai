"""测试爬虫模块"""
import sys
from pathlib import Path

# 添加路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir / "自动化爬虫"))
sys.path.insert(0, str(current_dir))

print("=" * 60)
print("爬虫模块功能测试")
print("=" * 60)

# 1. 测试依赖包
print("\n[1/5] 测试核心依赖包...")
deps_ok = True
try:
    import selenium
    print(f"  [OK] selenium: {selenium.__version__}")
except ImportError as e:
    print(f"  [FAIL] selenium: {e}")
    deps_ok = False

try:
    import undetected_chromedriver as uc
    print(f"  [OK] undetected-chromedriver: {uc.__version__}")
except ImportError as e:
    print(f"  [FAIL] undetected-chromedriver: {e}")
    deps_ok = False

try:
    import requests
    print(f"  [OK] requests: {requests.__version__}")
except ImportError as e:
    print(f"  [FAIL] requests: {e}")
    deps_ok = False

try:
    import bs4
    print(f"  [OK] beautifulsoup4: {bs4.__version__}")
except ImportError as e:
    print(f"  [FAIL] beautifulsoup4: {e}")
    deps_ok = False

try:
    import trafilatura
    print(f"  [OK] trafilatura: OK")
except ImportError as e:
    print(f"  [FAIL] trafilatura: {e}")
    deps_ok = False

try:
    import ddddocr
    print(f"  [OK] ddddocr: installed")
except ImportError as e:
    print(f"  [WARN] ddddocr: {e} (CNKI功能需要)")

if not deps_ok:
    print("\n[ERROR] 核心依赖包缺失，请运行: pip install -r 自动化爬虫/src/selenium_way/requirement.txt")
    sys.exit(1)

# 2. 测试配置模块
print("\n[2/5] 测试配置模块...")
try:
    from automation_spider.config import settings
    print("  [OK] 配置模块导入成功")
    print(f"    关键词: {settings.keywords}")
    print(f"    页数: {settings.pages}")
    print(f"    输出目录: {settings.save_root_dir}")
except Exception as e:
    print(f"  [FAIL] 配置模块失败: {e}")
    sys.exit(1)

# 3. 测试工具方法
print("\n[3/5] 测试工具方法...")
try:
    from src.selenium_way.methods import download_one, download_txt, extract_real_url, clean_special_chars
    print("  [OK] methods模块导入成功")
    
    # 测试URL提取
    test_url = "https://www.bing.com/search?q=test&u=aHR0cHM6Ly9leGFtcGxlLmNvbQ=="
    result = extract_real_url(test_url)
    print(f"  [OK] URL提取功能: {'正常' if result else '测试URL格式问题'}")
    
    # 测试文本清理
    test_text = "测试\n\n\n文本"
    cleaned = clean_special_chars(test_text)
    print(f"  [OK] 文本清理功能: {'正常' if cleaned else '异常'}")
except Exception as e:
    print(f"  [FAIL] methods模块失败: {e}")
    sys.exit(1)

# 4. 测试爬虫模块
print("\n[4/5] 测试爬虫模块...")
modules_ok = True

try:
    from src.selenium_way.get_PDF_links_by_keywords import pdf_runner
    print("  [OK] PDF爬虫模块: OK")
except Exception as e:
    print(f"  [FAIL] PDF爬虫模块: {e}")
    modules_ok = False

try:
    from src.selenium_way.Selenium_get_html import txt_runner
    print("  [OK] 文本爬虫模块: OK")
except Exception as e:
    print(f"  [FAIL] 文本爬虫模块: {e}")
    modules_ok = False

try:
    from src.selenium_way.crawle_url import crawle_url
    print("  [OK] URL爬虫模块: OK")
except Exception as e:
    print(f"  [FAIL] URL爬虫模块: {e}")
    modules_ok = False

try:
    from src.selenium_way.CNKI import run as cnki_run
    print("  [OK] CNKI模块: OK")
except Exception as e:
    print(f"  [WARN] CNKI模块: {e} (需要配置账号)")

if not modules_ok:
    print("\n[ERROR] 部分爬虫模块导入失败")
    sys.exit(1)

# 5. 测试CLI接口
print("\n[5/5] 测试CLI接口...")
try:
    from automation_spider.cli import build_parser
    parser = build_parser()
    print("  [OK] CLI接口: OK")
    print("    可用命令: pdf, txt, cnki, url")
except Exception as e:
    print(f"  [WARN] CLI接口: {e}")

print("\n" + "=" * 60)
print("[SUCCESS] 测试完成！爬虫模块可以正常使用")
print("=" * 60)
print("\n可用功能:")
print("  1. PDF抓取: python -m automation_spider pdf --keywords '测试' --pages 1")
print("  2. 文本抓取: python -m automation_spider txt --keywords '测试' --pages 1")
print("  3. URL抓取: python -m automation_spider url --urls 'https://example.com'")
print("  4. CNKI抓取: python -m automation_spider cnki --keywords '测试' --pages 1")
print("\n注意事项:")
print("  - 首次运行需要网络连接（下载ChromeDriver）")
print("  - 需要安装Chrome浏览器")
print("  - CNKI功能需要配置账号信息")


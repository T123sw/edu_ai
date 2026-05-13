"""
检索关键字找到pdf链接
"""
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from setup import timeout, SAVE_ROOT_DIR
import time
import random
import urllib.parse
import re
from methods import extract_real_url, extract_real_url_by_redirect, check_if_pdf_url

import os
from methods import download_all

class keywords_selenium:
    def __init__(self, output_path, keywords, search_engines=None):
        """
        Args:
            output_path: 输出路径
            keywords: 搜索关键词
            search_engines: 搜索引擎列表，默认为 ['bing', 'baidu']，可选值：'bing', 'baidu'
        """
        self.pdf_links = []
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")

        # 指定与本机 Chrome 版本 (142) 匹配的 chromedriver
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-infobars')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-site-isolation-trials')
        self.seen_links = set()
        self.output_path = output_path
        self.keywords = keywords
        self.search_engines = search_engines or ['bing', 'baidu']  # 默认使用 Bing 和百度
        #options.add_argument('--headless=new')

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
        options.add_argument(f"user-agent={user_agent}")
        
        # undetected_chromedriver会自动检测Chrome版本并下载匹配的ChromeDriver
        # 如果自动检测失败，可以指定version_main=142
        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)

    def split_keywords(self):
        keywords = self.keywords
        if isinstance(keywords, str):
            keywords = keywords.replace("，", ",")
            parts = [k.strip() for k in keywords.split(",") if k.strip()]
            self.keywords = parts

    def is_driver_alive(self):
        try:
            _ = self.driver.title
            return True
        except:
            return False

    def generate_search_queries(self, keyword):
        """生成多种搜索关键词格式"""
        queries = []
        # 格式1: filetype:pdf + 关键词
        queries.append(f'filetype:pdf {keyword}')
        # 格式2: "关键词" filetype:pdf
        queries.append(f'"{keyword}" filetype:pdf')
        # 格式3: 关键词 PDF
        queries.append(f'{keyword} PDF')
        # 格式4: 关键词 下载 PDF
        queries.append(f'{keyword} 下载 PDF')
        # 格式5: 关键词 课件 PDF
        queries.append(f'{keyword} 课件 PDF')
        # 格式6: 关键词 教材 PDF
        queries.append(f'{keyword} 教材 PDF')
        return queries
    
    def build_search_url(self, engine, query, page):
        """构建搜索引擎 URL"""
        if engine == 'bing':
            first = (page - 1) * 10 + 1
            return f'https://www.bing.com/search?q={urllib.parse.quote(query)}&first={first}'
        elif engine == 'baidu':
            pn = (page - 1) * 10
            return f'https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={pn}'
        else:
            raise ValueError(f"不支持的搜索引擎: {engine}")
    
    def get_result_container_selector(self, engine):
        """获取搜索结果容器的选择器"""
        if engine == 'bing':
            return (By.ID, "b_results")
        elif engine == 'baidu':
            return (By.ID, "content_left")
        else:
            raise ValueError(f"不支持的搜索引擎: {engine}")
    
    def get_result_item_selector(self, engine):
        """获取搜索结果项的选择器"""
        if engine == 'bing':
            return "#b_results li"
        elif engine == 'baidu':
            return "#content_left .result"
        else:
            raise ValueError(f"不支持的搜索引擎: {engine}")
    
    def get_title_link_selector(self, engine):
        """获取标题链接的选择器"""
        if engine == 'bing':
            return "h2 a"
        elif engine == 'baidu':
            return "h3 a, .t a"
        else:
            raise ValueError(f"不支持的搜索引擎: {engine}")
    
    def search(self, keyword, pages=1, startpage=0):
        """搜索 PDF 链接，支持多个搜索引擎和多种关键词格式"""
        self.pdf_links = []
        
        # 生成多种搜索关键词格式
        queries = self.generate_search_queries(keyword)
        print(f"\n为关键词 '{keyword}' 生成了 {len(queries)} 种搜索格式")
        
        # 遍历每个搜索引擎
        for engine in self.search_engines:
            print(f"\n{'='*60}")
            print(f"使用搜索引擎: {engine.upper()}")
            print(f"{'='*60}")
            
            # 遍历每种搜索格式
            for query_idx, query in enumerate(queries, 1):
                print(f"\n[搜索格式 {query_idx}/{len(queries)}] {query}")
                
                # 只搜索第一页（避免重复）
                if query_idx > 1:
                    search_pages = 1
                else:
                    search_pages = pages
                
                for page in range(startpage, search_pages + startpage):
                    try:
                        if not self.is_driver_alive():
                            self.restart_driver()

                        time.sleep(random.uniform(2, 5))
                        
                        url = self.build_search_url(engine, query, page + 1)
                        print(f"正在访问 {engine.upper()} 第 {page+1} 页: {url[:100]}...")
                        self.driver.get(url)

                        # 检查是否被重定向到登录页
                        if engine == 'bing':
                            if 'login.live.com' in self.driver.current_url or 'login.microsoft' in self.driver.current_url:
                                print("[WARN] 被重定向到登录页，跳过本页。")
                                continue
                        elif engine == 'baidu':
                            if 'passport.baidu.com' in self.driver.current_url:
                                print("[WARN] 被重定向到登录页，跳过本页。")
                                continue

                        # 等待搜索结果加载
                        container_selector = self.get_result_container_selector(engine)
                        wait = WebDriverWait(self.driver, 15)
                        wait.until(EC.presence_of_element_located(container_selector))
                        
                        # 等待页面完全加载
                        time.sleep(random.uniform(2, 3))
                        
                        # 滚动页面以触发懒加载
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(random.uniform(1, 2))
                        
                        # 再次滚动到顶部，确保所有元素加载
                        self.driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(random.uniform(0.5, 1))

                        # 查找 PDF 链接
                        self.look_for_pdf_links(engine)
                        
                        # 如果找到足够的 PDF，可以提前结束
                        if len(self.pdf_links) >= 20:
                            print(f"已找到 {len(self.pdf_links)} 个 PDF，提前结束搜索")
                            return

                    except Exception as e:
                        print(f"[WARN] {engine.upper()} 搜索失败，跳过: {e}")
                        continue

    def clean_filename(self, filename):
        """优化文件名清理，保留空格和常用分隔符"""
        clean_pattern = re.compile(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\-_]')
        cleaned_name = clean_pattern.sub('', filename)
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name)

        return cleaned_name.strip()[:100] or "cleaned_filename"

    def look_for_pdf_links(self, engine='bing'):
        """查找PDF链接，使用多种策略"""
        found_count = 0
        
        # 策略1: 使用Selenium直接查找链接元素
        try:
            # 等待搜索结果加载
            wait = WebDriverWait(self.driver, 10)
            result_selector = self.get_result_item_selector(engine)
            result_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, result_selector)))
            print(f"使用Selenium找到 {len(result_elements)} 个搜索结果项")
            
            # 先提取所有链接信息，避免 StaleElementReferenceException
            links_data = []
            title_selector = self.get_title_link_selector(engine)
            for idx, element in enumerate(result_elements, 1):
                try:
                    # 查找标题链接
                    title_link = element.find_element(By.CSS_SELECTOR, title_selector)
                    href = title_link.get_attribute('href')
                    title = title_link.text.strip()
                    if href:
                        links_data.append((idx, href, title))
                except Exception as e:
                    print(f"  [提取链接 {idx}] ❌ 异常: {type(e).__name__}: {str(e)}")
                    continue
            
            print(f"成功提取 {len(links_data)} 个链接，开始处理...")
            
            # 现在逐个处理链接（此时不会再有 StaleElementReferenceException）
            for idx, href, title in links_data:
                try:
                    
                    print(f"\n  [处理链接 {idx}] 标题: {title[:50]}...")
                    print(f"  [处理链接 {idx}] 原始 href: {href[:120] if href else 'None'}...")
                    
                    if not href:
                        print(f"  [处理链接 {idx}] ❌ 跳过：href 为空")
                        continue
                    
                    # 提取真实URL并检查是否为 PDF
                    is_ck_a = 'bing.com/ck/a' in (href or '')
                    is_baidu_link = 'baidu.com/link' in (href or '') or 'baidu.com/s?' in (href or '')
                    print(f"  [处理链接 {idx}] 是否为 /ck/a: {is_ck_a}, 是否为百度链接: {is_baidu_link}")
                    
                    if is_ck_a:
                        # 对于 /ck/a 链接，强制使用重定向解析
                        print(f"  [处理链接 {idx}] 调用 extract_real_url_by_redirect...")
                        r = extract_real_url_by_redirect(href, driver=self.driver)
                        print(f"  [处理链接 {idx}] extract_real_url_by_redirect 返回: {r[:100] if r else 'None'}...")
                        if r:
                            print(f"  [处理链接 {idx}] ✅ 重定向成功: {href[:60]}... -> {r[:80]}...")
                        else:
                            print(f"  [处理链接 {idx}] ❌ 重定向失败或非 PDF")
                        href_real = r
                        from_redirect = True
                    elif is_baidu_link:
                        # 百度链接需要跟踪重定向
                        print(f"  [处理链接 {idx}] 调用 check_if_pdf_url 跟踪百度链接...")
                        is_pdf, final_url = check_if_pdf_url(href, driver=self.driver)
                        print(f"  [处理链接 {idx}] check_if_pdf_url 返回: is_pdf={is_pdf}, final_url={final_url[:100] if final_url else 'None'}...")
                        if is_pdf:
                            href_real = final_url
                            from_redirect = True
                            print(f"  [处理链接 {idx}] ✅ PDF检测成功: {href[:60]}... -> {final_url[:80]}...")
                        else:
                            from_redirect = False
                            # 如果最终 URL 以 .pdf 结尾，也接受
                            if final_url and final_url.lower().endswith('.pdf'):
                                href_real = final_url
                                from_redirect = True
                                print(f"  [处理链接 {idx}] ✅ 最终 URL 以 .pdf 结尾: {final_url[:80]}...")
                            else:
                                print(f"  [处理链接 {idx}] ❌ 跳过：不是 PDF")
                                continue
                    else:
                        e = extract_real_url(href)
                        print(f"  [处理链接 {idx}] extract_real_url 返回: {e[:100] if e else 'None'}...")
                        href_real = e or href
                        print(f"  [处理链接 {idx}] href_real: {href_real[:100] if href_real else 'None'}...")
                        
                        # 对于非跳转链接，也检查是否为 PDF（可能重定向到 PDF）
                        if href_real and href_real.startswith('http'):
                            print(f"  [处理链接 {idx}] 调用 check_if_pdf_url...")
                            is_pdf, final_url = check_if_pdf_url(href_real, driver=self.driver)
                            print(f"  [处理链接 {idx}] check_if_pdf_url 返回: is_pdf={is_pdf}, final_url={final_url[:100] if final_url else 'None'}...")
                            if is_pdf:
                                href_real = final_url
                                from_redirect = True
                                print(f"  [处理链接 {idx}] ✅ PDF检测成功: {href[:60]}... -> {final_url[:80]}...")
                            else:
                                from_redirect = False
                                # 如果最终 URL 以 .pdf 结尾，也接受
                                if final_url and final_url.lower().endswith('.pdf'):
                                    href_real = final_url
                                    from_redirect = True
                                    print(f"  [处理链接 {idx}] ✅ 最终 URL 以 .pdf 结尾: {final_url[:80]}...")
                                elif not href_real.lower().endswith('.pdf'):
                                    print(f"  [处理链接 {idx}] ❌ 跳过：不是 PDF 且 URL 不以 .pdf 结尾")
                                    continue
                                else:
                                    print(f"  [处理链接 {idx}] ⚠️ URL 以 .pdf 结尾，但 check_if_pdf_url 返回 False")
                        else:
                            print(f"  [处理链接 {idx}] ❌ 跳过：href_real 无效")
                            continue
                    
                    if not href_real:
                        print(f"  [处理链接 {idx}] ❌ 跳过：href_real 为空")
                        continue
                    
                    if href_real in self.seen_links:
                        print(f"  [处理链接 {idx}] ❌ 跳过：已存在")
                        continue
                    
                    cleaned_title = self.clean_filename(title) or f"PDF_{found_count + 1}"
                    self.seen_links.add(href_real)
                    self.pdf_links.append({
                        "name": cleaned_title,
                        "href": href_real
                    })
                    
                    found_count += 1
                    print(f"  [处理链接 {idx}] ✅✅✅ 找到PDF [{found_count}]: {cleaned_title[:50]}... -> {href_real[:80]}...")
                    
                except Exception as e:
                    # 单个元素处理失败，继续下一个
                    print(f"  [处理链接 {idx}] ❌ 异常: {type(e).__name__}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
                    
        except Exception as e:
            print(f"Selenium查找失败: {e}，尝试使用BeautifulSoup...")
        
        # 若本页一个都未找到，打印第一个链接样本便于调试
        if found_count == 0:
            try:
                if engine == 'bing':
                    selector = "#b_results li h2 a"
                elif engine == 'baidu':
                    selector = "#content_left .result h3 a, #content_left .result .t a"
                else:
                    selector = "a"
                el = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if el:
                    sample = el[0].get_attribute('href') or ''
                    if sample:
                        print(f"  [调试] 第一个链接样本: {sample[:120]}...")
            except Exception:
                pass
        
        # 策略2: 如果Selenium失败，使用BeautifulSoup
        if found_count == 0:
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            if engine == 'bing':
                container = soup.select_one('#b_results')
            elif engine == 'baidu':
                container = soup.select_one('#content_left')
            else:
                container = None
            
            if container:
                if engine == 'bing':
                    result_items = container.select('li')
                    link_selectors = 'h2 > a, h2 a, a[href*=".pdf"]'
                elif engine == 'baidu':
                    result_items = container.select('.result')
                    link_selectors = 'h3 a, .t a, a[href*=".pdf"]'
                else:
                    result_items = []
                    link_selectors = 'a[href*=".pdf"]'
                
                print(f"使用BeautifulSoup找到 {len(result_items)} 个搜索结果项")
                
                for part in result_items:
                    links = part.select(link_selectors)
                    
                    for idx_bs, link in enumerate(links, 1):
                        href = link.get('href')
                        title = (link.text or '').strip()
                        
                        print(f"\n  [BeautifulSoup-处理链接 {idx_bs}] 标题: {title[:50]}...")
                        print(f"  [BeautifulSoup-处理链接 {idx_bs}] 原始 href: {href[:120] if href else 'None'}...")
                        
                        if not href:
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：href 为空")
                            continue
                        
                        # 提取真实URL并检查是否为 PDF（同上）
                        is_ck_a = 'bing.com/ck/a' in (href or '')
                        is_baidu_link = 'baidu.com/link' in (href or '') or 'baidu.com/s?' in (href or '')
                        print(f"  [BeautifulSoup-处理链接 {idx_bs}] 是否为 /ck/a: {is_ck_a}, 是否为百度链接: {is_baidu_link}")
                        
                        if is_ck_a:
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] 调用 extract_real_url_by_redirect...")
                            r = extract_real_url_by_redirect(href, driver=self.driver)
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] extract_real_url_by_redirect 返回: {r[:100] if r else 'None'}...")
                            if r:
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] ✅ 重定向成功: {href[:60]}... -> {r[:80]}...")
                            else:
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 重定向失败或非 PDF")
                            href_real = r
                            from_redirect = True
                        elif is_baidu_link:
                            # 百度链接需要跟踪重定向
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] 调用 check_if_pdf_url 跟踪百度链接...")
                            is_pdf, final_url = check_if_pdf_url(href, driver=self.driver)
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] check_if_pdf_url 返回: is_pdf={is_pdf}, final_url={final_url[:100] if final_url else 'None'}...")
                            if is_pdf:
                                href_real = final_url
                                from_redirect = True
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] ✅ PDF检测成功: {href[:60]}... -> {final_url[:80]}...")
                            else:
                                from_redirect = False
                                if final_url and final_url.lower().endswith('.pdf'):
                                    href_real = final_url
                                    from_redirect = True
                                    print(f"  [BeautifulSoup-处理链接 {idx_bs}] ✅ 最终 URL 以 .pdf 结尾: {final_url[:80]}...")
                                else:
                                    print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：不是 PDF")
                                    continue
                        else:
                            e = extract_real_url(href)
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] extract_real_url 返回: {e[:100] if e else 'None'}...")
                            href_real = e or href
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] href_real: {href_real[:100] if href_real else 'None'}...")
                            
                            # 对于非 /ck/a 链接，也检查是否为 PDF
                            if href_real and href_real.startswith('http'):
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] 调用 check_if_pdf_url...")
                                is_pdf, final_url = check_if_pdf_url(href_real, driver=self.driver)
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] check_if_pdf_url 返回: is_pdf={is_pdf}, final_url={final_url[:100] if final_url else 'None'}...")
                                if is_pdf:
                                    href_real = final_url
                                    from_redirect = True
                                    print(f"  [BeautifulSoup-处理链接 {idx_bs}] ✅ PDF检测成功: {href[:60]}... -> {final_url[:80]}...")
                                else:
                                    from_redirect = False
                                    # 如果最终 URL 以 .pdf 结尾，也接受
                                    if final_url and final_url.lower().endswith('.pdf'):
                                        href_real = final_url
                                        from_redirect = True
                                        print(f"  [BeautifulSoup-处理链接 {idx_bs}] ✅ 最终 URL 以 .pdf 结尾: {final_url[:80]}...")
                                    elif not href_real.lower().endswith('.pdf'):
                                        print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：不是 PDF 且 URL 不以 .pdf 结尾")
                                        continue
                                    else:
                                        print(f"  [BeautifulSoup-处理链接 {idx_bs}] ⚠️ URL 以 .pdf 结尾，但 check_if_pdf_url 返回 False")
                            else:
                                print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：href_real 无效")
                                continue
                        
                        if not href_real:
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：href_real 为空")
                            continue
                        
                        if href_real in self.seen_links:
                            print(f"  [BeautifulSoup-处理链接 {idx_bs}] ❌ 跳过：已存在")
                            continue
                        
                        cleaned_title = self.clean_filename(title) or f"PDF_{found_count + 1}"
                        self.seen_links.add(href_real)
                        self.pdf_links.append({
                            "name": cleaned_title,
                            "href": href_real
                        })
                        
                        found_count += 1
                        print(f"找到PDF [{found_count}]: {cleaned_title[:50]}... -> {href_real[:80]}...")
            else:
                print("未找到搜索结果容器 #b_results")
                # 保存页面源码用于调试
                try:
                    debug_file = os.path.join(self.output_path, "debug_page.html")
                    os.makedirs(os.path.dirname(debug_file), exist_ok=True)
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    print(f"调试信息已保存到: {debug_file}")
                except:
                    pass
        
        if found_count == 0:
            print("本页未找到PDF链接")
            print("提示: 可以检查保存的debug_page.html文件查看页面结构")

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except OSError:
                pass
            self.driver = None
            print("浏览器已关闭")

    def restart_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except OSError:
                pass
            self.driver = None

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # undetected_chromedriver会自动管理ChromeDriver版本
        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)

    def run(self, pages=1, startpage=0):
        k = self.keywords.replace(",", "_")
        k = k.replace("，", "_")
        output_path = os.path.join(self.output_path, f"output/{k}/collect/pdf")
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        all_links = []
        self.split_keywords()
        for keyword in self.keywords:
            self.search(keyword, pages, startpage)
            all_links.extend(self.pdf_links)
            print(f"{keyword}找到{len(self.pdf_links)}个pdf")
        if self.driver:
            try:
                self.driver.quit()
            except OSError:
                pass
            self.driver = None

        download_all(output_path, all_links)


def pdf_runner(path, keywords, pages=1, startpage=0, search_engines=None):
    """
    Args:
        path: 输出路径
        keywords: 搜索关键词
        pages: 搜索页数
        startpage: 起始页码
        search_engines: 搜索引擎列表，默认为 ['bing', 'baidu']
    """
    cra = keywords_selenium(output_path=path, keywords=keywords, search_engines=search_engines)
    cra.run(pages=pages, startpage=startpage)



if __name__ == '__main__':
    keywords1 = "材料力学"
    c = keywords_selenium(output_path=SAVE_ROOT_DIR, keywords=keywords1)
    c.run()
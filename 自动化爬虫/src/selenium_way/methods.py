import os
import requests
import base64
from urllib.parse import urlparse, parse_qs, unquote
import concurrent.futures
import re
import time

def safe_b64decode(encoded_str):
    """安全的Base64解码函数，自动处理填充和URL安全编码"""
    if not encoded_str:
        return None
    if encoded_str.startswith('a1'):
        encoded_str = encoded_str[2:]
    missing_padding = len(encoded_str) % 4
    if missing_padding != 0:
        encoded_str += '=' * (4 - missing_padding)

    try:
        # 使用URL安全的Base64解码
        decoded_bytes = base64.urlsafe_b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        print(f"Base64解码错误: {e}")
        try:
            decoded_bytes = base64.b64decode(encoded_str)
            return decoded_bytes.decode('utf-8')
        except Exception as e2:
            print(f"标准Base64解码也失败: {e2}")
            return None


def extract_real_url(bing_url):
    """
    从Bing跳转链接中提取真实URL（增强版）
    支持多种Bing链接格式：
    1. 直接URL（已经是真实URL，非bing域名）
    2. Bing跳转 /ck/a 格式：u=, a1=, p= 等参数
    3. URL编码的直接链接
    """
    if not bing_url:
        return None
    
    try:
        # 已经是非Bing的完整URL，直接返回
        if (bing_url.startswith('http://') or bing_url.startswith('https://')):
            if 'bing.com' not in bing_url and 'microsoft' not in bing_url:
                return bing_url
            
            # Bing跳转链接，尝试多种参数
            if 'bing.com' in bing_url:
                parsed = urlparse(bing_url)
                qs = parse_qs(parsed.query)
                # 尝试 u, a1, p 等常见Bing跳转参数
                for param in ('u', 'a1', 'p', 'rurl'):
                    enc = qs.get(param, [None])[0]
                    if enc:
                        # 先尝试URL解码（可能被encode了两次）
                        enc = unquote(enc)
                        real = safe_b64decode(enc)
                        if real and (real.startswith('http') or real.startswith('//')):
                            if real.startswith('//'):
                                real = 'https:' + real
                            return real
                # 如果 parse_qs 没找到参数（可能是 /ck/a 的 !&& 格式），继续到下面的手动解析
                # /ck/a 格式：?!&&p=xxx 或 &&p=xxx
                # 注意：Bing 的 /ck/a 现在使用令牌格式（p= 不是 Base64 URL），必须用重定向解析
                # 但先尝试检查是否有 u= 参数（旧格式可能还有）
                if '/ck/a' in parsed.path:
                    raw = (parsed.query or '') + (('&' + parsed.fragment) if parsed.fragment else '')
                    # 先尝试 u= 参数（如果有，可能是旧格式）
                    for part in raw.replace('!', '&').split('&'):
                        if '=' in part:
                            k, v = part.split('=', 1)
                            k = k.strip()
                            if k == 'u':  # u= 参数可能是直接 URL 或 Base64
                                enc = unquote(v.strip())
                                real = safe_b64decode(enc)
                                if real and (real.startswith('http') or real.startswith('//')):
                                    if real.startswith('//'):
                                        real = 'https:' + real
                                    return real
                                # 如果 u= 不是 Base64，可能是直接 URL
                                if enc.startswith('http'):
                                    return enc
                    # /ck/a 没有 u= 参数或解析失败，返回 None 让调用方用重定向解析
                    return None
                if '/search' in parsed.path:
                    return None
                # 其他 Bing 链接，返回 None 让调用方处理
                return None
        
        if bing_url.startswith('/'):
            return None
        return None
    except Exception:
        return None


def check_if_pdf_url(url, driver=None):
    """
    检查 URL 是否为 PDF（通过跟踪重定向和检查 Content-Type）。
    返回 (is_pdf, final_url) 元组，is_pdf 为 True 表示是 PDF。
    """
    if not url or not url.startswith('http'):
        return (False, None)
    
    print(f"    [check_if_pdf_url] 开始检查: {url[:100]}...")
    
    # 优先用 Selenium driver 跟踪（已有浏览器环境，更可靠）
    if driver:
        try:
            current = driver.current_url
            print(f"    [check_if_pdf_url] 当前页面: {current[:100]}...")
            print(f"    [check_if_pdf_url] 访问链接...")
            driver.get(url)
            import time
            time.sleep(2)  # 等待重定向完成
            final = driver.current_url
            print(f"    [check_if_pdf_url] 最终 URL: {final[:100]}...")
            
            # 返回原页面
            if current and current != final:
                print(f"    [check_if_pdf_url] 返回原页面...")
                driver.get(current)
                time.sleep(0.5)
            elif current:
                driver.back()
                time.sleep(0.5)
            
            if 'login.' in final or 'microsoft.com' in final.lower():
                print(f"    [check_if_pdf_url] ❌ 被重定向到登录页")
                return (False, None)
            # 检查是否为 PDF：URL 包含 .pdf
            if final.lower().endswith('.pdf') or '.pdf' in final.lower():
                print(f"    [check_if_pdf_url] ✅ URL 包含 .pdf")
                return (True, final)
            # 对最终 URL 用 requests 检查 Content-Type
            if final and not final.startswith('https://www.bing.com'):
                try:
                    import requests
                    print(f"    [check_if_pdf_url] 检查 Content-Type...")
                    hd = requests.head(final, timeout=5, allow_redirects=False,
                                     headers={'User-Agent': 'Mozilla/5.0'})
                    ct = (hd.headers.get('Content-Type') or '').lower()
                    print(f"    [check_if_pdf_url] Content-Type: {ct}")
                    if 'application/pdf' in ct:
                        print(f"    [check_if_pdf_url] ✅ Content-Type 是 application/pdf")
                        return (True, final)
                    else:
                        print(f"    [check_if_pdf_url] ❌ Content-Type 不是 application/pdf，尝试从 HTML 页面提取 PDF 链接...")
                        # 如果是 HTML 页面，尝试提取其中的 PDF 链接（此时 driver 还在目标页面）
                        if 'text/html' in ct and driver:
                            pdf_links = extract_pdf_links_from_html(driver, final, already_on_page=True)
                            if pdf_links:
                                # 返回第一个 PDF 链接
                                print(f"    [check_if_pdf_url] ✅ 从 HTML 页面找到 {len(pdf_links)} 个 PDF 链接，返回第一个")
                                return (True, pdf_links[0])
                except Exception as e:
                    print(f"    [check_if_pdf_url] ❌ 检查 Content-Type 失败: {e}")
            else:
                print(f"    [check_if_pdf_url] ❌ 最终 URL 是 Bing 页面")
            return (False, final)
        except Exception as e:
            print(f"    [check_if_pdf_url] ❌ Selenium 跟踪失败: {e}")
            import traceback
            traceback.print_exc()
            pass  # 失败则回退到 requests
    
    # 回退到 requests
    try:
        import requests
        r = requests.head(url, allow_redirects=True, timeout=8,
                          headers={'User-Agent': 'Mozilla/5.0'})
        final = r.url
        if 'login.' in final or 'microsoft.com' in final.lower():
            return (False, None)
        ct = (r.headers.get('Content-Type') or '').lower()
        if 'application/pdf' in ct:
            return (True, final)
        if final.lower().endswith('.pdf') or '.pdf' in final.lower():
            return (True, final)
        return (False, final)
    except Exception:
        return (False, None)


def extract_pdf_links_from_html(driver, url, already_on_page=False):
    """
    从 HTML 页面中提取 PDF 下载链接。
    返回 PDF 链接列表，如果没有找到则返回空列表。
    
    Args:
        driver: Selenium WebDriver 实例
        url: 要提取 PDF 链接的页面 URL
        already_on_page: 如果为 True，表示 driver 已经在该页面上，不需要再次访问
    """
    if not driver:
        return []
    
    try:
        from bs4 import BeautifulSoup
        import re
        
        current = driver.current_url
        if not already_on_page:
            print(f"    [extract_pdf_links_from_html] 访问页面提取 PDF 链接: {url[:100]}...")
            driver.get(url)
            import time
            time.sleep(2)  # 等待页面加载
        else:
            print(f"    [extract_pdf_links_from_html] 从当前页面提取 PDF 链接: {url[:100]}...")
            import time
            time.sleep(1)  # 等待页面完全加载
        
        # 解析页面内容
        soup = BeautifulSoup(driver.page_source, 'lxml')
        pdf_links = []
        seen = set()  # 去重
        
        # 方法1: 查找所有 <a> 标签的 href 属性
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href:
                continue
            
            # 处理相对链接
            if href.startswith('/'):
                from urllib.parse import urljoin
                href = urljoin(url, href)
            elif not href.startswith('http'):
                continue
            
            # 检查是否是 PDF 链接
            if '.pdf' in href.lower() or href.lower().endswith('.pdf'):
                if href not in seen:
                    pdf_links.append(href)
                    seen.add(href)
                    print(f"    [extract_pdf_links_from_html] 找到 PDF 链接 (a标签): {href[:100]}...")
        
        # 方法2: 查找所有包含 PDF 的属性（data-href, data-url, data-src 等）
        pdf_attrs = ['href', 'data-href', 'data-url', 'data-src', 'data-link', 'data-file', 'src']
        for attr in pdf_attrs:
            for elem in soup.find_all(attrs={attr: re.compile(r'\.pdf', re.I)}):
                href = elem.get(attr, '').strip()
                if href and href not in seen:
                    if href.startswith('/'):
                        from urllib.parse import urljoin
                        href = urljoin(url, href)
                    if href.startswith('http') and ('.pdf' in href.lower() or href.lower().endswith('.pdf')):
                        pdf_links.append(href)
                        seen.add(href)
                        print(f"    [extract_pdf_links_from_html] 找到 PDF 链接 ({attr}): {href[:100]}...")
        
        # 方法3: 在页面文本中查找 PDF URL（正则表达式）
        page_text = driver.page_source
        pdf_url_pattern = re.compile(r'https?://[^\s<>"\'\)]+\.pdf', re.I)
        for match in pdf_url_pattern.finditer(page_text):
            href = match.group(0)
            if href not in seen:
                pdf_links.append(href)
                seen.add(href)
                print(f"    [extract_pdf_links_from_html] 找到 PDF 链接 (文本匹配): {href[:100]}...")
        
        # 方法4: 查找 <iframe> 和 <embed> 标签中的 PDF
        for tag in soup.find_all(['iframe', 'embed', 'object']):
            src = tag.get('src', '').strip() or tag.get('data', '').strip()
            if src and ('.pdf' in src.lower() or src.lower().endswith('.pdf')):
                if src.startswith('/'):
                    from urllib.parse import urljoin
                    src = urljoin(url, src)
                if src.startswith('http') and src not in seen:
                    pdf_links.append(src)
                    seen.add(src)
                    print(f"    [extract_pdf_links_from_html] 找到 PDF 链接 ({tag.name}): {src[:100]}...")
        
        # 返回原页面（如果之前不在该页面上）
        if not already_on_page:
            if current and current != driver.current_url:
                driver.get(current)
                time.sleep(0.5)
            elif current:
                driver.back()
                time.sleep(0.5)
        
        print(f"    [extract_pdf_links_from_html] 共找到 {len(pdf_links)} 个 PDF 链接")
        return pdf_links
        
    except Exception as e:
        print(f"    [extract_pdf_links_from_html] ❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        # 尝试返回原页面
        try:
            if current and current != driver.current_url:
                driver.get(current)
                time.sleep(0.5)
        except:
            pass
        return []


def extract_real_url_by_redirect(bing_url, driver=None):
    """
    通过 HTTP 重定向获取 Bing /ck/a 的真实 URL。
    Bing 的 p= 已改为令牌格式（非 Base64 URL），必须跟踪 302 才能拿到真实地址。
    优先使用 Selenium driver（更可靠），否则用 requests。
    仅当最终响应为 PDF（Content-Type 或 URL 以 .pdf 结尾）时返回，否则返回 None。
    """
    if not bing_url or 'bing.com/ck/a' not in bing_url:
        return None
    
    print(f"    [extract_real_url_by_redirect] 开始处理: {bing_url[:100]}...")
    
    # 优先用 Selenium driver 跟踪（已有浏览器环境，更可靠）
    if driver:
        try:
            current = driver.current_url
            print(f"    [extract_real_url_by_redirect] 当前页面: {current[:100]}...")
            print(f"    [extract_real_url_by_redirect] 访问链接...")
            driver.get(bing_url)
            import time
            time.sleep(2)  # 等待重定向完成
            final = driver.current_url
            print(f"    [extract_real_url_by_redirect] 最终 URL: {final[:100]}...")
            
            if 'login.' in final or 'microsoft.com' in final.lower():
                print(f"    [extract_real_url_by_redirect] ❌ 被重定向到登录页")
                # 返回原页面
                if current and current != final:
                    driver.get(current)
                    time.sleep(0.5)
                return None
            
            # 检查是否为 PDF：URL 包含 .pdf 或 Content-Type 是 application/pdf
            if final.lower().endswith('.pdf') or '.pdf' in final.lower():
                print(f"    [extract_real_url_by_redirect] ✅ URL 包含 .pdf")
                # 返回原页面
                if current and current != final:
                    driver.get(current)
                    time.sleep(0.5)
                return final
            
            # 对最终 URL 用 requests 检查 Content-Type（避免 CORS）
            if final and not final.startswith('https://www.bing.com'):
                try:
                    import requests
                    print(f"    [extract_real_url_by_redirect] 检查 Content-Type...")
                    hd = requests.head(final, timeout=5, allow_redirects=False,
                                     headers={'User-Agent': 'Mozilla/5.0'})
                    ct = (hd.headers.get('Content-Type') or '').lower()
                    print(f"    [extract_real_url_by_redirect] Content-Type: {ct}")
                    if 'application/pdf' in ct:
                        print(f"    [extract_real_url_by_redirect] ✅ Content-Type 是 application/pdf")
                        # 返回原页面
                        if current and current != final:
                            driver.get(current)
                            time.sleep(0.5)
                        return final
                    else:
                        print(f"    [extract_real_url_by_redirect] ❌ Content-Type 不是 application/pdf，尝试从 HTML 页面提取 PDF 链接...")
                        # 如果是 HTML 页面，尝试提取其中的 PDF 链接（此时 driver 还在目标页面）
                        if 'text/html' in ct and driver:
                            pdf_links = extract_pdf_links_from_html(driver, final, already_on_page=True)
                            if pdf_links:
                                # 返回第一个 PDF 链接
                                print(f"    [extract_real_url_by_redirect] ✅ 从 HTML 页面找到 {len(pdf_links)} 个 PDF 链接，返回第一个")
                                return pdf_links[0]
                except Exception as e:
                    print(f"    [extract_real_url_by_redirect] ❌ 检查 Content-Type 失败: {e}")
            else:
                print(f"    [extract_real_url_by_redirect] ❌ 最终 URL 是 Bing 页面")
            
            # 返回原页面
            if current and current != final:
                driver.get(current)
                time.sleep(0.5)
            elif current:
                driver.back()
                time.sleep(0.5)
            
            return None
        except Exception as e:
            print(f"    [extract_real_url_by_redirect] ❌ Selenium 跟踪失败: {e}")
            import traceback
            traceback.print_exc()
            pass  # 失败则回退到 requests
    
    # 回退到 requests
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bing.com/',
        'Accept': 'text/html,application/pdf,*/*;q=0.8',
    }
    try:
        r = requests.get(bing_url, allow_redirects=True, stream=True, timeout=12, headers=_headers)
        try:
            r.close()
        except Exception:
            pass
        final = r.url
        if 'login.' in final or 'microsoft.com' in final.lower():
            return None
        ct = (r.headers.get('Content-Type') or '').lower()
        if 'application/pdf' in ct:
            return final
        if final.lower().endswith('.pdf') or '.pdf' in final.lower():
            return final
        return None
    except Exception as e:
        return None



def download_one(args):
    output_path, url, filename = args
    filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    if not filename:
        filename = f"pdf_{int(time.time())}"
    filepath = os.path.join(output_path, filename + ".pdf")

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(r.content)

        print(f"下载成功：{filename}")
        return True
    except Exception as e:
        print(f"下载失败 {filename}: {e}")
        return False


def clean_special_chars(text: str) -> str:
    if not text:
        return ""
    cleaned_text = re.sub(
        r'[^\u0020-\uFFFF]',
        '',
        text
    )

    char_map = {
        '\u30fb': '·',
        '\u200b': '',
        '\u00a0': ' ',
        '\r\n': '\n',
        '\r': '\n'
    }

    for old_char, new_char in char_map.items():
        cleaned_text = cleaned_text.replace(old_char, new_char)

    cleaned_text = re.sub(r'\n+', '\n', cleaned_text)
    cleaned_text = re.sub(r' +', ' ', cleaned_text)

    return cleaned_text.strip()

def download_txt(args):
    output_path, text, filename = args
    filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    save_path = os.path.join(output_path, filename) + ".txt"
    count = 1
    while os.path.exists(save_path):
        save_path = os.path.join(output_path, f"{filename}_{count}.txt")
        count += 1

    text = clean_special_chars(text)
    try:
        with open(save_path, "w",encoding="utf-8") as f:
            f.write(text)
        print(f"保存完成：{filename}")
        return True
    except:
        return False


def download_all(output_path, url_list, max_workers=10):
    """
    max_workers=10 → 启动10线程并发下载
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    tasks = [(output_path, item["href"], item["name"]) for item in url_list]

    success = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for ok in pool.map(download_one, tasks):
            if ok:
                success += 1

    print(f"全部完成：共 {len(url_list)} 个，成功 {success} 个。")

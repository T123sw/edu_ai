"""
用selenium登录校园carsi，并批量抓取论文详情页地址，之后用requests下载论文
"""
import urllib
import requests
import os
import random
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import ddddocr
import base64
from urllib.parse import quote
from setup import password, username, college, SAVE_ROOT_DIR, CNKI_MAXWORKERS
from concurrent.futures import ThreadPoolExecutor, as_completed

# 识别验证码
def get_ocr(data_url):
    """
    将Data URL格式的验证码图片解析为文本
    :param data_url: 数据URL字符串
    :return: 识别出的验证码文本
    """
    ocr = ddddocr.DdddOcr(show_ad=False)

    if '%0A' in data_url:
        data_url = data_url.replace('%0A', '')

    base64_data = data_url.split(',')[1]
    img_bytes = base64.b64decode(base64_data)
    captcha_text = ocr.classification(img_bytes)

    return captcha_text

def refresh_verify_code(driver):
    """刷新验证码图片（重试时调用）"""
    try:
        verify_code_img = driver.find_element(By.XPATH,
            "/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[3]/div/table/tr/td[2]/img")
        verify_code_img.click()  # 点击图片刷新
        time.sleep(1)
    except Exception as e:
        print(f"刷新验证码失败：{e}")

def input_verify_code(driver):
    """输入验证码"""
    verify_code_input = driver.find_element(By.XPATH,
        "/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[3]/div/table/tr/td[1]/div/input")
    verify_code_input.clear()
    # 获取验证码图片DataURL
    data_url = driver.find_element(By.XPATH,
        "/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[3]/div/table/tr/td[2]/img").get_attribute('src')
    captcha_text = get_ocr(data_url)
    verify_code_input.send_keys(captcha_text)
    return captcha_text

def init_carsi_login():
    """
    Selenium 完成 CARSI 登录，返回登录后的 driver（含有效会话）
    """
    carsi_url = "https://fsso.cnki.net/"
    options = webdriver.ChromeOptions()
    # 使用webdriver-manager自动检测Chrome版本（CNKI使用标准selenium，不是undetected）
    service = ChromeService(ChromeDriverManager().install())
    # options.add_argument("--headless=new")  # 调试时注释，可视化登录过程
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()  # 最大化窗口，避免元素被遮挡
    driver.get(carsi_url)
    wait = WebDriverWait(driver, 15)

    try:
        # 输入学校名称
        school_input = wait.until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/div[1]/div[2]/input'))
        )
        school_input.clear()
        school_input.send_keys(college)
        time.sleep(1)

        # 点击下一步
        next_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/div[1]/div[2]/div[2]'))
        )
        next_btn.click()
        time.sleep(3)

        # 等待登录页面加载
        # if "cas/login" not in driver.current_url:
        #     print("未跳转到学校登录页面，可能学校名称输入错误")
        #     driver.quit()
        #     return None

        # 输入账号密码
        username_input = wait.until(EC.presence_of_element_located((
            By.XPATH, '/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[1]/div/input'
        )))
        password_input = wait.until(EC.presence_of_element_located((
            By.XPATH, '/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[2]/div/input'
        )))
        username_input.clear()
        password_input.clear()
        username_input.send_keys(username)
        password_input.send_keys(password)


        max_attempts = 3
        while max_attempts > 0:
            captcha_text = input_verify_code(driver)
            print(f"尝试验证码：{captcha_text}")
            # 点击登录
            login_button = wait.until(
                EC.element_to_be_clickable((By.XPATH,
                    '/html/body/div[1]/div/div[2]/div[1]/div[2]/div/form/li[4]/input[1]'))
            )
            login_button.click()
            time.sleep(2)

            try:
                error_element = driver.find_element(By.XPATH, "//*[contains(text(), '验证码输入有误')]")
                if error_element.is_displayed():
                    print(f" 验证码错误：{captcha_text}，剩余重试次数：{max_attempts-1}")
                    max_attempts -= 1
                    refresh_verify_code(driver)  # 刷新验证码
                    continue
            except:
                # 无验证码错误，登录成功
                print("登录成功（验证码验证通过）")
                break

        if max_attempts == 0:
            print("验证码重试次数耗尽，登录失败")
            driver.quit()
            return None

        try:
            choice = wait.until(EC.element_to_be_clickable((
                By.XPATH, '/html/body/form/div/div[2]/div/p[3]/input'
            )))
            choice.click()
            time.sleep(1)
        except:
            pass

        try:
            accept_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, '/html/body/form/div/div[2]/p[2]/input[2]'
            )))
            accept_button.click()
            time.sleep(3)
        except:
            pass

        # 验证最终登录状态
        if "cnki.net" in driver.current_url:
            print("CARSI登录全程完成，已进入知网")
            return driver
        else:
            print(" 登录后未跳转到知网")
            driver.quit()
            return None

    except Exception as e:
        print(f"登录过程异常：{e}")
        driver.quit()
        return None

def crawl_single_paper_links(html):
    """
    解析单页HTML，提取论文详情页链接
    修复：BeautifulSoup的Tag用get("href")而非get_attribute
    """
    link_list = []
    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.find_all('a', class_='fz14')
    for a_tag in a_tags:
        title = a_tag.text.strip()
        detail_url = a_tag.get("href")  # 核心修复：替换get_attribute
        if title and detail_url:
            # 补全相对路径
            if not detail_url.startswith("http"):
                detail_url = urllib.parse.urljoin("https://kns.cnki.net", detail_url)
            link_list.append({"title": title, "detail_url": detail_url})
            print(f"收集到详情页：{title[:20]}... - {detail_url[:50]}...")
    return link_list

def crawl_paper_links(driver, keyword, pages=1):
    """
    多页抓取论文详情页链接（优化翻页逻辑）
    """
    detail_url_list = []
    encode_keyword = quote(keyword)
    search_url = (
        f"https://kns.cnki.net/kns8s/defaultresult/index?"
        "crossids=YSTT4HG0%2CLSTPFY1C%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA"
        "%2CBLZOG7CK%2CPWFIRAGL%2CEMRPGLPA%2CNLBO1Z6R%2CNN3FJMUV&korder=SU&"
        f"kw={encode_keyword}"
    )
    driver.get(search_url)
    wait = WebDriverWait(driver, 15)

    for page in range(pages):
        print(f"\n开始抓取第 {page+1} 页论文链接")
        # 等待当前页内容加载
        try:
            wait.until(EC.presence_of_all_elements_located((
                By.XPATH, '//a[@class="fz14" and @href]'
            )))
        except Exception as e:
            print(f"第 {page+1} 页内容加载失败：{e}")
            break

        html = driver.page_source
        tmp = crawl_single_paper_links(html)
        detail_url_list.extend(tmp)
        print(f"第 {page+1} 页抓取完成，新增 {len(tmp)} 个链接")

        if page < pages - 1:
            try:

                page_down_button = wait.until(EC.element_to_be_clickable((
                    By.XPATH, '/html/body/div[2]/div[2]/div[2]/div[2]/div/div[1]/div/div[1]/span[3]/a'
                )))
                page_down_button.click()
                time.sleep(random.uniform(2, 3))
            except Exception as e:
                print(f"第 {page+1} 页翻页失败：{e}")
                break

    print(f"\n总计抓取到 {len(detail_url_list)} 个论文详情页链接")
    return detail_url_list


def get_download_url_from_detail_url(driver, detail_url):
    """用 Selenium Driver 访问详情页，提取 PDF 下载链接（无需额外 Chromium）"""
    try:
        driver.get(detail_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "PDF下载")]'))
        )
        pdf_btn = driver.find_element(By.XPATH, '//a[contains(text(), "PDF下载")]')
        if pdf_btn:
            download_url = pdf_btn.get_attribute("href")
            if not download_url.startswith("http"):
                download_url = urllib.parse.urljoin("https://kns.cnki.net", download_url)
            return download_url
        else:
            return None
    except Exception as e:
        print(f"解析detail_url失败：{detail_url[:50]}... - {str(e)}")
        return None

def get_safe_save_path(save_dir, paper_title):
    """生成安全的保存路径：清理非法字符 + 避免文件名重复"""
    illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\t', '\n']
    safe_title = "".join([c for c in paper_title if c not in illegal_chars])
    if len(safe_title) > 50:
        safe_title = safe_title[:50]
    base_path = os.path.join(save_dir, f"{safe_title}.pdf")
    save_path = base_path
    count = 1
    while os.path.exists(save_path):
        save_path = os.path.join(save_dir, f"{safe_title}_{count}.pdf")
        count += 1
    return save_path


def download_pdf_task(selenium_cookies, download_url, paper_title, save_dir):
    """单个PDF下载任务"""
    session = requests.Session()
    for cookie in selenium_cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain")
        )
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://kns.cnki.net/",
        "Accept": "application/pdf, */*"
    })

    save_path = get_safe_save_path(save_dir, paper_title)
    if os.path.exists(save_path):
        session.close()
        return (paper_title, "skipped", save_path)

    try:
        print(f"开始下载：{paper_title[:20]}...")
        response = session.get(download_url, stream=True, timeout=30)

        if response.status_code != 200:
            session.close()
            return (paper_title, "failed", f"状态码 {response.status_code}")

        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            session.close()
            return (paper_title, "failed", f"非PDF文件（{content_type}）")

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        session.close()
        time.sleep(random.uniform(1, 2))
        return (paper_title, "success", save_path)

    except Exception as e:
        session.close()
        return (paper_title, "failed", str(e))


def run(output_path, keyword, pages):
    """主执行函数"""
    output_path = os.path.normpath(output_path)
    output_abs_path = os.path.abspath(output_path)
    os.makedirs(output_abs_path, exist_ok=True)
    print(f"开始执行知网下载任务：关键词={keyword}，页数={pages}，保存路径={output_path}")
    print(f"绝对保存路径：{output_abs_path}")
    #登录CARSI
    driver = init_carsi_login()
    if not driver:
        print("CARSI登录失败，任务终止")
        return

    detailed_paper_urls = crawl_paper_links(driver, keyword, pages)
    if not detailed_paper_urls:
        print(" 未抓取到任何论文详情页链接，任务终止")
        driver.quit()
        return

    paper_download_list = []
    selenium_cookies = driver.get_cookies()
    print(f"\n开始提取PDF下载链接（共{len(detailed_paper_urls)}个详情页）...")

    for idx, paper in enumerate(detailed_paper_urls, 1):
        title = paper["title"]
        detail_url = paper["detail_url"]
        # 用 Selenium Driver 解析详情页（无需额外 Chromium）
        download_url = get_download_url_from_detail_url(driver, detail_url)

        if download_url and "bar.cnki.net" in download_url:
            paper_download_list.append({
                "title": title,
                "download_url": download_url
            })
            print(f"[{idx}/{len(detailed_paper_urls)}] 提取成功：{title[:20]}... - {download_url[:50]}...")
        else:
            print(f"[{idx}/{len(detailed_paper_urls)}]  无PDF链接：{title[:20]}...")

        time.sleep(random.uniform(0.5, 1.5))  # 反爬延时

    driver.quit()
    print(f"\n解析完成，共提取到 {len(paper_download_list)} 个PDF下载链接")

    if not paper_download_list:
        print("未提取到任何PDF下载链接，任务终止")
        return

    print(f"\n开始线程池下载（{CNKI_MAXWORKERS}个线程），共{len(paper_download_list)}个任务")
    results = []
    success = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=CNKI_MAXWORKERS) as executor:
        future_to_paper = {
            executor.submit(
                download_pdf_task,
                selenium_cookies,
                paper["download_url"],
                paper["title"],
                output_path
            ): paper for paper in paper_download_list
        }

        for future in as_completed(future_to_paper):
            try:
                title, status, msg = future.result()
                results.append((title, status, msg))
                if status == "success":
                    success += 1
                    print(f"下载成功：{title[:20]}... → {msg}")
                elif status == "failed":
                    failed += 1
                    print(f"下载失败：{title[:20]}... → {msg}")
                elif status == "skipped":
                    skipped += 1
                    print(f"已下载跳过：{title[:20]}... → {msg}")
            except Exception as e:
                paper = future_to_paper[future]
                print(f"任务异常：{paper['title'][:20]}... → {str(e)}")
                failed += 1

    print("\n=========== CNKI下载完成 ===========")
    print(f"总任务数：{len(paper_download_list)}")
    print(f"成功下载：{success}")
    print(f"下载失败：{failed}")
    print(f"已下载跳过：{skipped}")
    print(f"文件保存至：{output_abs_path}")

# 调用示例
if __name__ == "__main__":
    keyword = "操作系统"
    download_pages = 1
    save_path = os.path.join(SAVE_ROOT_DIR, "output", keyword, "CNKI")
    save_path = os.path.normpath(save_path)
    run(save_path, keyword, pages=download_pages)
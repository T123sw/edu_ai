"""
抓取网页正文，并在保存文本时同步保存网页图片。
"""
import os
import random
import re
import time
import urllib.parse

import trafilatura
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from methods import download_images_from_page, download_txt
from setup import timeout


class Request_by_Selenium:
    def __init__(self, keywords, output_path):
        self.keywords = keywords
        keyword_dir = self.keywords.replace(",", "_").replace("，", "_")
        self.output_path = os.path.join(output_path, "output", keyword_dir, "collect", "text")
        self.links = []

        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )

        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)

    def restart_driver(self):
        try:
            self.driver.quit()
        except Exception:
            pass

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")

        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)

    def is_driver_alive(self):
        try:
            _ = self.driver.title
            return True
        except Exception:
            return False

    def clean_keywords(self, keywords):
        return [k.strip() for k in keywords.split(",") if k.strip()]

    def clean_filename(self, filename):
        clean_pattern = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9]")
        cleaned_name = clean_pattern.sub("", filename)
        cleaned_name = cleaned_name[:100].strip()
        return cleaned_name or "cleaned_filename"

    def get_search_results(self, pages=3):
        keywords = self.clean_keywords(self.keywords)
        all_links = []

        for keyword in keywords:
            for page in range(pages):
                if not self.is_driver_alive():
                    self.restart_driver()

                time.sleep(random.uniform(1, 3))
                first = page * 10 + 1
                search_url = (
                    "https://cn.bing.com/academic/search?"
                    f"q={urllib.parse.quote(keyword)}&first={first}&FORM=PENR1"
                )

                try:
                    print(f"[INFO] 正在访问: {search_url}")
                    self.driver.get(search_url)
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#b_results"))
                    )
                    time.sleep(random.uniform(1.2, 2.5))
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    all_links.extend(self.extract_links())
                except Exception as e:
                    print("[ERROR] 访问搜索结果时发生错误:", e)

        print(f"[INFO] 共获取到 {len(all_links)} 个链接\n")
        self.links = all_links

    def extract_links(self):
        soup = BeautifulSoup(self.driver.page_source, "lxml")
        results = soup.select_one("#b_results")
        extracted = []

        if not results:
            return extracted

        for item in results.find_all("li"):
            anchor = item.select_one("h2 > a")
            if not anchor:
                continue

            title = anchor.text.strip()
            url = anchor.get("href")
            if not url:
                continue

            extracted.append(
                {
                    "title": self.clean_filename(title),
                    "href": url,
                }
            )

        return extracted

    def fetch_text_from_url(self, url):
        try:
            self.driver.get(url)
            time.sleep(random.uniform(2, 4))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
            html = self.driver.page_source
            html = html.encode("utf-8", errors="replace").decode("utf-8")
            text = trafilatura.extract(html, include_comments=False, include_tables=False)
            return text or "", html
        except Exception as e:
            print("[ERROR] 抓取正文失败:", e)
            return "", ""

    def run(self, pages=1):
        self.get_search_results(pages)
        all_links = self.links
        os.makedirs(self.output_path, exist_ok=True)
        print(f"[INFO] 开始抓取正文，共 {len(all_links)} 篇网页...\n")

        success = 0
        image_count = 0

        for idx, info in enumerate(all_links, 1):
            print(f"正在抓取第 {idx} 个文件: {info['title']}")
            url = info["href"]
            text, html = self.fetch_text_from_url(url)

            image_output_path = os.path.join(
                os.path.dirname(self.output_path),
                "images",
                info["title"],
            )
            saved_images = download_images_from_page(
                output_dir=image_output_path,
                html=html,
                page_url=url,
                page_name=info["title"],
            )
            if saved_images:
                image_count += len(saved_images)
                print(f"[INFO] 已保存 {len(saved_images)} 张网页图片")

            if len(text) > 100:
                if download_txt((self.output_path, text, info["title"])):
                    success += 1
                    print("[INFO] 正文保存成功")
            elif saved_images:
                success += 1
                print("[INFO] 正文较短，但已保存网页图片")
            else:
                print("[INFO] 内容过短，跳过")

        print(f"一共 {len(all_links)} 个链接，成功处理 {success} 个页面，另外下载 {image_count} 张图片")
        self.driver.quit()

    def close_driver(self):
        self.driver.quit()


def txt_runner(path, keywords, pages=1):
    crawler = Request_by_Selenium(keywords, path)
    crawler.run(pages)


if __name__ == "__main__":
    keyword = "生物学"
    output_root = "C:\\Users\\28573\\Desktop\\python_for_pachong"
    crawler = Request_by_Selenium(keyword, output_root)
    crawler.run()

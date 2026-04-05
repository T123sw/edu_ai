import threading
import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
from setup import *


class IPSource:
    def __init__(self):
        self.url = ip_url
        self.headers = {
            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'
        }
        self.proxies = []  # 存储所有抓取的代理
        self.valid_proxies = []  # 存储有效代理（需线程安全操作）
        self.lock = threading.Lock()  # 线程锁：保护 valid_proxies 的写入安全

    def get_free_proxies(self):
        """抓取免费代理IP"""
        url = self.url
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print("访问IP网站时出现问题：", e)
            return

        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.select("table.table tbody tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) >= 2:
                ip = tds[0].text.strip()
                port = tds[1].text.strip()
                proxy = f"http://{ip}:{port}"
                self.proxies.append(proxy)

        print(f"获取到 {len(self.proxies)} 个代理IP")

    def check_proxy(self, proxy):
        """验证单个代理是否可用（线程安全，无共享资源操作）"""
        test_url = "http://httpbin.org/ip"
        proxy_dict = {"http": proxy, "https": proxy}
        try:
            response = requests.get(test_url, proxies=proxy_dict, timeout=7)
            if response.status_code == 200:
                print(f"代理 {proxy} 验证成功")
                return True
        except Exception:
            print(f"代理 {proxy} 验证失败")
            return False
        return False

    def batch_check_proxy(self, proxy_subset):
        """批量验证代理子集（供单个线程调用）"""
        for proxy in proxy_subset:
            if self.check_proxy(proxy):
                # 写入 valid_proxies 时加锁，避免多线程同时修改导致数据混乱
                with self.lock:
                    self.valid_proxies.append(proxy)

    def multi_thread_check(self, thread_num=4):
        """多线程验证所有代理：将代理列表拆分给多个线程"""
        if not self.proxies:
            print("没有可验证的代理列表")
            return

        # 1. 清空历史有效代理（避免与本次结果混合）
        self.valid_proxies = []
        # 2. 拆分代理列表：将 self.proxies 平均分给 thread_num 个线程
        proxy_chunks = self._split_list(self.proxies, thread_num)
        # 3. 创建线程列表
        threads = []
        for chunk in proxy_chunks:
            # 每个线程处理一个代理子集，传入当前 IPSource 实例（共享锁和 valid_proxies）
            thread = threading.Thread(target=self.batch_check_proxy, args=(chunk,))
            threads.append(thread)
            thread.start()

        # 4. 等待所有线程执行完毕
        for thread in threads:
            thread.join()

        print(f"多线程验证完成，筛选出 {len(self.valid_proxies)} 个可用代理")

    def _split_list(self, origin_list, split_num):
        """辅助方法：将列表平均拆分为 N 个子列表（用于线程分配）"""
        chunk_size = (len(origin_list) + split_num - 1) // split_num  # 向上取整，避免遗漏
        return [origin_list[i:i + chunk_size] for i in range(0, len(origin_list), chunk_size)]

    def get_valid_proxies(self):
        """获取有效代理"""
        return self.valid_proxies

    def save_proxies(self, file_path="valid_proxies.csv"):
        """保存有效代理到CSV（逻辑不变，确保 valid_proxies 已生成）"""
        if not self.valid_proxies:
            print("没有有效代理可保存，请先执行 multi_thread_check 方法")
            return

        fieldnames = ["proxy_ip", "is_valid", "save_time"]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(file_path, mode="a+", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            f.seek(0)
            if not f.readline():
                writer.writeheader()

            for proxy in self.valid_proxies:
                writer.writerow({
                    "proxy_ip": proxy,
                    "is_valid": "是",
                    "save_time": current_time
                })

        print(f"有效代理已成功保存到 {file_path}，共 {len(self.valid_proxies)} 条数据")


# ------------------- 测试使用（简化调用逻辑） -------------------
if __name__ == "__main__":
    ip_source = IPSource()
    # 1. 抓取代理
    ip_source.get_free_proxies()
    # 2. 多线程验证（默认4个线程，可调整 thread_num 参数）
    ip_source.multi_thread_check(thread_num=10)
    # 3. 保存有效代理
    ip_source.save_proxies()
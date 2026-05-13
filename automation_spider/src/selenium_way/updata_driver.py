from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager

# 强制从国内镜像下载142版本驱动，不使用旧缓存
service = Service(
    ChromeDriverManager(
        url="https://npm.taobao.org/mirrors/chromedriver/",  # 国内镜像
        cache_manager=DriverCacheManager()  # 清空后重新缓存新驱动
    ).install()
)
driver = webdriver.Chrome(service=service)
driver.get("https://www.baidu.com")  # 测试是否正常启动
"""
爬虫模块的兼容性setup配置
当automation_spider.config不存在时使用此配置
"""
import os
from pathlib import Path

# 默认配置
timeout = 10
pdf_max_workers = 10
cnki_max_workers = 3

# 其他可能需要的配置
save_root_dir = os.getenv("SPIDER_SAVE_ROOT_DIR", "./output")


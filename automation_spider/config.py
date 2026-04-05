"""统一配置模块，代替旧的 selenium_way.setup。
可通过环境变量或命令行覆盖。
"""
from dataclasses import dataclass, field
import os
from typing import Optional


def _env(key: str, default: Optional[str] = None):
    return os.getenv(key, default)


@dataclass
class Settings:
    # selenium 等公用配置
    timeout: int = int(_env("SPIDER_TIMEOUT", 10))

    # 下载线程数
    pdf_max_workers: int = int(_env("PDF_MAX_WORKERS", 10))
    cnki_max_workers: int = int(_env("CNKI_MAX_WORKERS", 3))

    # 账号信息（若需要）
    password: str = _env("CNKI_PASSWORD", "##########")
    username: str = _env("CNKI_USERNAME", "2024------")
    college: str = _env("CNKI_COLLEGE", "哈尔滨工程大学")

    # 默认任务参数（可由 CLI 覆盖）
    keywords: str = _env("SPIDER_KEYWORDS", "线性规划")
    pages: int = int(_env("SPIDER_PAGES", 1))

    save_root_dir: str = _env("SAVE_ROOT_DIR", os.path.join(os.getcwd(), "output"))

    # 其他
    ip_url: str = _env("IP_URL", "https://free-proxy-list.net/")
    ip_list: list[str] = field(default_factory=list)

    urls: str = _env("SPIDER_URLS", "")


settings = Settings()

# 兼容旧代码：暴露变量名
for _key, _val in settings.__dict__.items():
    globals()[_key] = _val

# 旧代码通常使用全大写 `SAVE_ROOT_DIR`，这里做别名兼容
SAVE_ROOT_DIR = save_root_dir
CNKI_MAXWORKERS = cnki_max_workers  # CNKI模块兼容

# 向后兼容：允许旧代码 `import setup` 或 `from setup import x`
import sys as _sys
_sys.modules.setdefault("setup", _sys.modules[__name__])

# 清理临时变量
del _key, _val, _env, _sys

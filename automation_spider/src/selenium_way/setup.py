"""兼容旧代码的配置文件。

现在统一使用 `automation_spider.config.settings`。
本文件仅作向下兼容，未来将被移除。
"""
from automation_spider.config import settings  # type: ignore

# 直接把 settings 中的属性暴露为同名变量，供旧代码 `from setup import x` 使用
globals().update(settings.__dict__)

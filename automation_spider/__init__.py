"""automation_spider 统一抓取包

提供统一的 CLI 入口以及配置读取。
在保持原 selenium_way 代码不动的前提下，通过包装层统一调用。
"""

from importlib import metadata

__version__ = "0.1.0"

# 向外暴露 CLI 方便 `python -m automation_spider` 直接运行
from .cli import main  # noqa: E402

# ------- 兼容旧 selenium_way 顶级模块名 -------
import sys as _sys
from importlib import import_module as _import_module

# 将 selenium_way.methods 映射为顶级 methods
try:
    _methods_mod = _import_module("automation_spider.src.selenium_way.methods")
    _sys.modules.setdefault("methods", _methods_mod)
except ModuleNotFoundError:
    pass

del _sys, _import_module

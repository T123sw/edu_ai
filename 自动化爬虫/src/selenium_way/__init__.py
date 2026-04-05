# selenium_way 子包标识，并将内部 methods 模块暴露为顶级别名
import sys as _sys
from importlib import import_module as _import_module

_methods_mod = _import_module(__name__ + ".methods")
_sys.modules.setdefault("methods", _methods_mod)

del _sys, _import_module

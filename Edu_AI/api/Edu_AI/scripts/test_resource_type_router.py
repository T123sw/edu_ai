from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = PROJECT_ROOT / "app" / "chat" / "resource_type_router.py"

spec = importlib.util.spec_from_file_location("resource_type_router", ROUTER_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
ResourceTypeRouter = module.ResourceTypeRouter


class _MockGateway:
    def __init__(self, response):
        self.response = response

    def chat(self, messages, temperature=0.0, max_tokens=40):
        return self.response


def run() -> None:
    # 1) LLM JSON 正常返回
    router = ResourceTypeRouter(_MockGateway('{"resource_type":"lesson_plan"}'))
    rt, source = router.classify("帮我生成一份高一物理教案")
    assert rt == "lesson_plan", (rt, source)
    assert source.startswith("llm:"), source

    # 2) LLM 非法返回 -> 关键词兜底
    router = ResourceTypeRouter(_MockGateway('{"resource_type":"unknown"}'))
    rt, source = router.classify("请做一个课程PPT课件")
    assert rt == "ppt", (rt, source)
    assert source.startswith("keyword:"), source

    # 3) 无关键词 -> 默认 report
    router = ResourceTypeRouter(_MockGateway('invalid-json'))
    rt, source = router.classify("给点建议")
    assert rt == "report", (rt, source)
    assert source.startswith("fallback:"), source

    # 4) 无 gateway -> 直接关键词兜底
    router = ResourceTypeRouter(None)
    rt, source = router.classify("帮我写一篇博客文章")
    assert rt == "blog", (rt, source)
    assert source.startswith("keyword:"), source

    print("resource_type_router tests passed")


if __name__ == "__main__":
    run()

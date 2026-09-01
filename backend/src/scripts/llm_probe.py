import os
import json
from typing import Dict

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate


class ProbeSchema(BaseModel):
    core_topic: str = Field(description="核心主题")
    focus_area: str = Field(description="聚焦方向")
    confidence: float = Field(description="提取置信度，0.0到1.0")


TEST_PROMPT = "请从这句话中提取信息：我要写一篇关于人工智能的报告，重点探讨大模型在教育领域的应用。"


class LLMCapabilityProbe:
    def __init__(self, model_name: str, api_base: str, api_key: str):
        self.model_name = model_name
        self.api_base = api_base
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_base=api_base,
            openai_api_key=api_key,
            temperature=0.1,
            max_retries=0,
        )
        self.report: Dict[str, str] = {}

    def run_all_tests(self) -> None:
        print(f"\n🚀 开始探测模型能力: [{self.model_name}]")
        print(f"🔗 API Base: {self.api_base}\n" + "=" * 52)

        self.report["Native_JSON_Schema"] = self._test_json_schema()
        self.report["Tool_Calling"] = self._test_tool_calling()
        self.report["Plain_JSON_Parsing"] = self._test_plain_json()

        self._print_matrix()

    def _short_error(self, e: Exception) -> str:
        return str(e).split("\n")[0][:120]

    def _test_json_schema(self) -> str:
        print("▶️ 测试 1: Native JSON Schema (response_format)... ", end="")
        try:
            structured_llm = self.llm.with_structured_output(ProbeSchema, method="json_schema")
            res = structured_llm.invoke([HumanMessage(content=TEST_PROMPT)])
            _ = res.model_dump() if hasattr(res, "model_dump") else str(res)
            print("✅ 成功")
            return "✅ 支持"
        except Exception as e:
            err_msg = self._short_error(e)
            print(f"❌ 失败 ({err_msg}...)")
            return f"❌ 失败 ({err_msg})"

    def _test_tool_calling(self) -> str:
        print("▶️ 测试 2: Tool Calling (function_calling)... ", end="")
        try:
            structured_llm = self.llm.with_structured_output(ProbeSchema, method="function_calling")
            res = structured_llm.invoke([HumanMessage(content=TEST_PROMPT)])
            _ = res.model_dump() if hasattr(res, "model_dump") else str(res)
            print("✅ 成功")
            return "✅ 支持"
        except Exception as e:
            err_msg = self._short_error(e)
            print(f"❌ 失败 ({err_msg}...)")
            return f"❌ 失败 ({err_msg})"

    def _test_plain_json(self) -> str:
        print("▶️ 测试 3: Plain JSON Prompting + Parser... ", end="")
        try:
            parser = JsonOutputParser(pydantic_object=ProbeSchema)
            prompt = PromptTemplate(
                template=(
                    "你是一个提取器。\n"
                    "{format_instructions}\n"
                    "用户输入：{query}\n"
                    "只输出 JSON。"
                ),
                input_variables=["query"],
                partial_variables={"format_instructions": parser.get_format_instructions()},
            )
            chain = prompt | self.llm | parser
            res = chain.invoke({"query": TEST_PROMPT})
            _ = json.dumps(res, ensure_ascii=False)
            print("✅ 成功")
            return "✅ 支持"
        except Exception as e:
            err_msg = self._short_error(e)
            print(f"❌ 失败 ({err_msg}...)")
            return f"❌ 失败 ({err_msg})"

    def _print_matrix(self) -> None:
        print("\n📊 结构化能力兼容性矩阵 (Compatibility Matrix):")
        print("-" * 60)
        print(f"{'测试模式':<28} | {'测试结果'}")
        print("-" * 60)
        for mode, result in self.report.items():
            print(f"{mode:<28} | {result}")
        print("-" * 60 + "\n")


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


if __name__ == "__main__":
    # 用法示例：
    # set OPENROUTER_API_KEY=xxx
    # python scripts/llm_probe.py

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        probe = LLMCapabilityProbe(
            model_name=os.getenv("PROBE_MODEL", "openai/gpt-5.4-mini"),
            api_base=os.getenv("PROBE_BASE", "https://openrouter.ai/api/v1"),
            api_key=openrouter_key,
        )
        probe.run_all_tests()
    else:
        print("未检测到 OPENROUTER_API_KEY，跳过 OpenRouter 探针。")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        probe2 = LLMCapabilityProbe(
            model_name=os.getenv("PROBE_MODEL_DEEP", "deepseek-chat"),
            api_base=os.getenv("PROBE_BASE_DEEP", "https://api.deepseek.com/v1"),
            api_key=deepseek_key,
        )
        probe2.run_all_tests()
    else:
        print("未检测到 DEEPSEEK_API_KEY，跳过 DeepSeek 探针。")

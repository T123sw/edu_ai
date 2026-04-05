"""
测试结构化输出，诊断问题
"""
from o_agent import get_llm_from_config
from o_agent.types import Thought
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
import json

print("=" * 60)
print("测试结构化输出")
print("=" * 60)

# 获取LLM
llm = get_llm_from_config(temperature=0.2)

# 测试1: 使用json_schema方法
print("\n测试1: 使用json_schema方法")
print("-" * 60)
try:
    structured_llm = llm.with_structured_output(Thought, method='json_schema')
    messages = [
        SystemMessage(content="你是一个AI助手，需要返回你的思考。"),
        HumanMessage(content="请思考一下接下来该做什么。"),
        AIMessage(content='我应该思考一下接下来该做什么...')
    ]
    resp = structured_llm.invoke(messages)
    print(f"✅ 成功!")
    print(f"返回类型: {type(resp)}")
    print(f"thought字段: {resp.thought}")
    print(f"完整对象: {resp}")
except Exception as e:
    print(f"❌ 失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 测试2: 使用普通LLM调用，然后手动解析
print("\n测试2: 使用普通LLM调用，然后手动解析")
print("-" * 60)
try:
    messages = [
        SystemMessage(content="你是一个AI助手，需要返回JSON格式的思考。格式：{\"thought\": \"你的思考内容\"}"),
        HumanMessage(content="请思考一下接下来该做什么，返回JSON格式。"),
    ]
    resp = llm.invoke(messages)
    print(f"LLM原始响应: {resp.content}")
    
    # 尝试解析JSON
    import re
    json_match = re.search(r'\{[^}]+\}', resp.content)
    if json_match:
        json_str = json_match.group()
        data = json.loads(json_str)
        thought_obj = Thought(**data)
        print(f"✅ 手动解析成功!")
        print(f"thought字段: {thought_obj.thought}")
    else:
        print("❌ 未找到JSON格式")
except Exception as e:
    print(f"❌ 失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 测试3: 使用function_calling方法（如果支持）
print("\n测试3: 使用function_calling方法")
print("-" * 60)
try:
    structured_llm = llm.with_structured_output(Thought, method='function_calling')
    messages = [
        SystemMessage(content="你是一个AI助手，需要返回你的思考。"),
        HumanMessage(content="请思考一下接下来该做什么。"),
    ]
    resp = structured_llm.invoke(messages)
    print(f"✅ 成功!")
    print(f"返回类型: {type(resp)}")
    print(f"thought字段: {resp.thought}")
except Exception as e:
    print(f"❌ 失败: {type(e).__name__}: {e}")
    print("注意: function_calling方法可能不支持")

print("\n" + "=" * 60)


import ast
import inspect
import json
import re
import logging
from typing import List, Literal, Dict, Any
from jinja2 import FileSystemLoader
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from datetime import datetime
from .llm import get_llm_by_type
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph,START,END
from .types import State,Thought
from langgraph.checkpoint.memory import MemorySaver
from jinja2.environment import Environment
from pathlib import Path
from langchain_core.tools import tool
import operator as op
import os
import io
from contextlib import redirect_stdout, redirect_stderr
from .types import Tokenizer
# from .token_counter import count_langchain_messages

logger = logging.getLogger(__name__)

env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent/Path('prompt'))),
    autoescape=False,
    trim_blocks=False,
    lstrip_blocks=False
)

def get_template_by_name(name: str, params: dict) -> str:
    params_ = {
        'current_time': datetime.now(),
        **params,
    }
    template = env.get_template(name+'.md')
    prompt = template.render(**params_)
    return prompt

@tool
def chat(response: str) -> None:
    """
    唯一与用户交流的方式
    :param response: 你对用户的回复
    :return: None
    """
    return None



class BaseAgent(object):



    base_tools = [chat]
    checkpointer = MemorySaver()
    def __init__(self, name: str, llm: BaseChatModel, tools: List, prompt:str=None):
        self.name = name
        self.llm = llm
        self.tools = tools+self.base_tools
        self.prompt = prompt
        self.tokenizer = Tokenizer()


        self.tool_schemas = [self.export_openai_tool_schema(x) for x in self.tools]


        self.TOOLS_MAP = {x.name: x for x in self.tools}

        def thought_node(state: State, config: RunnableConfig) -> Command[Literal['action']]:

            print(f"当前token：{state['count']}")

            _llm = self.llm.with_structured_output(Thought, method='json_schema', include_raw=True)
            _state = {
                'tools':self.tool_schemas
            }
            system_prompt = get_template_by_name('thought', _state)
            messages = []
            for t in state['messages']:
                for m in t:
                    messages.append(m)

            messages += [SystemMessage(content=system_prompt)]

            # 优化：改进结构化输出，添加更好的错误处理和重试逻辑
            resp = None
            max_tries = 3  # 增加重试次数，确保成功
            
            for attempt in range(max_tries):
                try:
                    # 方法1: 尝试使用json_schema方法
                    resp = _llm.invoke(messages)

                    parsed = None
                    raw_content = None
                    if isinstance(resp, dict):
                        parsed = resp.get("parsed")
                        raw = resp.get("raw")
                        raw_content = getattr(raw, "content", None) if raw else None
                    else:
                        parsed = getattr(resp, "parsed", None)
                        raw = getattr(resp, "raw", None)
                        raw_content = getattr(raw, "content", None) if raw else getattr(resp, "content", None)

                    thought_value = None
                    if parsed and isinstance(parsed, dict):
                        thought_value = parsed.get("thought")
                    elif parsed and hasattr(parsed, "thought"):
                        thought_value = getattr(parsed, "thought", None)

                    if thought_value:
                        print(f"[{state['step']}] [thought]{thought_value}")
                        return Command(
                            update={"thought": thought_value},
                            goto="action",
                        )

                    if raw_content:
                        raw_content = str(raw_content).strip()
                        if raw_content:
                            print(f"[{state['step']}] [thought]{raw_content} (raw)")
                            return Command(
                                update={"thought": raw_content},
                                goto="action",
                            )

                    # 如果返回的对象没有thought字段，继续重试
                    logger.warning(f"结构化输出返回的对象缺少thought字段，尝试 {attempt + 1}/{max_tries}")
                    continue
                        
                except Exception as e:
                    # 如果json_schema方法失败，尝试手动解析
                    logger.warning(f"结构化输出失败 (尝试 {attempt + 1}/{max_tries}): {type(e).__name__}: {e}")
                    
                    if attempt < max_tries - 1:
                        # 最后一次尝试：使用普通LLM调用，然后手动解析JSON
                        try:
                            # 添加明确的JSON格式要求
                            json_prompt = SystemMessage(content="你必须返回一个有效的JSON对象，格式：{\"thought\": \"你的思考内容\"}。不要有任何额外的文本或格式。")
                            fallback_messages = messages[:-1] + [json_prompt, messages[-1]]
                            
                            normal_resp = self.llm.invoke(fallback_messages)
                            content = normal_resp.content if hasattr(normal_resp, 'content') else str(normal_resp)
                            
                            # 尝试从响应中提取JSON（re和json已在顶部导入）
                            # 方法1: 直接解析整个内容
                            try:
                                data = json.loads(content)
                                if isinstance(data, dict) and 'thought' in data:
                                    thought_obj = Thought(**data)
                                    print(f"[{state['step']}] [thought]{thought_obj.thought} (手动解析)")
                                    return Command(
                                        update={'thought': thought_obj.thought},
                                        goto='action'
                                    )
                            except json.JSONDecodeError:
                                pass
                            
                            # 方法2: 使用正则表达式提取JSON（支持多行和嵌套）
                            # 匹配 {"thought": "..."} 格式，支持多行和嵌套的JSON值
                            json_match = re.search(r'\{[^{}]*(?:"thought"\s*:\s*"[^"]*")[^{}]*\}', content, re.DOTALL)
                            # 如果简单匹配失败，尝试更宽松的匹配
                            if not json_match:
                                json_match = re.search(r'\{[^{}]*"thought"\s*:\s*"[^"]*"[^{}]*\}', content, re.DOTALL)
                            if json_match:
                                try:
                                    json_str = json_match.group()
                                    data = json.loads(json_str)
                                    if 'thought' in data:
                                        thought_obj = Thought(**data)
                                        print(f"[{state['step']}] [thought]{thought_obj.thought} (正则解析)")
                                        return Command(
                                            update={'thought': thought_obj.thought},
                                            goto='action'
                                        )
                                except (json.JSONDecodeError, Exception):
                                    pass
                            
                            # 方法3: 如果找不到JSON，尝试提取纯文本作为thought
                            # 清理内容，移除可能的markdown格式
                            clean_content = re.sub(r'```json\s*', '', content)
                            clean_content = re.sub(r'```\s*', '', clean_content)
                            clean_content = clean_content.strip()
                            
                            if clean_content and len(clean_content) > 0:
                                # 如果内容看起来像思考文本，直接使用
                                if len(clean_content) < 500:  # 合理的思考长度
                                    print(f"[{state['step']}] [thought]{clean_content[:100]}... (文本提取)")
                                    return Command(
                                        update={'thought': clean_content},
                                        goto='action'
                                    )
                        except Exception as e2:
                            logger.warning(f"手动解析也失败: {type(e2).__name__}: {e2}")
                            continue
                    else:
                        # 最后一次尝试也失败
                        continue

            # 所有尝试都失败，使用fallback
            fallback_thought = "继续执行搜索任务"
            print(f"[{state['step']}] [thought]{fallback_thought}")
            return Command(
                update={"thought": fallback_thought},
                goto="action",
            )
            # if self.name == 'reporter':
            #     # EVENT_Q.put(
            #     #     (
            #     #         'deepresearch',
            #     #         'reporter',
            #     #         f'[{state['step']}] [thought]{resp.thought}'
            #     #     )
            #     # )
            print(f"[{state['step']}] [thought]{resp.thought}")

            return Command(
                update={
                    'thought':resp.thought,
                },
                goto='action'
            )
            # if self.name == 'reporter':
            #     # EVENT_Q.put(
            #     #     (
            #     #         'deepresearch',
            #     #         'reporter',
            #     #         f'[{state['step']}] [thought]{resp.thought}'
            #     #     )
            #     # )
            print(f"[{state['step']}] [thought]{resp.thought}")

            return Command(
                update={
                    'thought':resp.thought,
                },
                goto='action'
            )


        def action_node(state: State, config: RunnableConfig) -> Command[Literal['tool','reflex']]:


            params_ = {
                'current_time': datetime.now(),
                'current_thought': state['thought'],
            }
            action_prompt = get_template_by_name('action', params_)
            messages = []
            for t in state["messages"]:
                for m in t:
                    messages.append(m)

            if self.prompt:
                messages = [HumanMessage(content=self.prompt)] + messages



            messages = messages + [SystemMessage(content=action_prompt)]
            _llm = self.llm.bind_tools(self.tools, tool_choice='auto')

            #ai_m = AIMessage(content=f'{state["thought"]}')
            #ai_m.name = 'thought'
            #messages += [ai_m]
            #messages += [SystemMessage(content='只有使用`chat`工具才能与用户交互')]
            resp = _llm.invoke(messages)
            # if self.name == 'reporter':
            #     EVENT_Q.put(
            #         (
            #             'deepresearch',
            #             'reporter',
            #             f'[{state['step']}] [action]{resp.content}'
            #         )
            #     )

            print(f'[{state['step']}] [action]{resp.content}')
            tool_calls = resp.tool_calls
            resp.name = 'action'
            
            # 验证tool_calls格式
            if tool_calls:
                # 确保tool_calls是列表
                if not isinstance(tool_calls, list):
                    logger.warning(f"tool_calls格式不正确: {type(tool_calls)}, 转换为列表")
                    tool_calls = []
                else:
                    # 验证每个tool_call的格式
                    valid_tool_calls = []
                    for tc in tool_calls:
                        if isinstance(tc, dict) and 'name' in tc:
                            # 验证工具名是否有效
                            tool_name = tc.get('name', '')
                            original_tool_name = tool_name
                            
                            # 清理工具名，移除可能的特殊标记
                            if tool_name and tool_name not in self.TOOLS_MAP:
                                if '<tool_sep>' in tool_name or '<tool_call' in tool_name:
                                    # 尝试提取第一个工具名
                                    match = re.search(r'^([a-zA-Z_][a-zA-Z0-9_]*)', tool_name)
                                    if match:
                                        tool_name = match.group(1)
                                        tc['name'] = tool_name  # 更新tool_call中的工具名
                                        logger.info(f"清理工具名: {original_tool_name[:50]} -> {tool_name}")
                            
                            if tool_name and tool_name in self.TOOLS_MAP:
                                valid_tool_calls.append(tc)
                            else:
                                logger.warning(f"无效的工具名: {original_tool_name[:50]}, 可用工具: {list(self.TOOLS_MAP.keys())}")
                        else:
                            logger.warning(f"无效的tool_call格式: {type(tc)}, 跳过")
                    tool_calls = valid_tool_calls
                    
                    # 更新resp.tool_calls为清理后的版本
                    resp.tool_calls = tool_calls
            
            if len(tool_calls) > 0:
                return Command(
                    update={
                        'current_message': resp,
                        # 'count': count_langchain_messages([resp]),
                    },
                    goto='tool'
                )

            if state.get('step', 0)%100==0:
                return Command(

                    update={
                        'messages': (resp,),
                        'current_message': None,
                        'step': state.get('step', 0)+1,
                        # 'count': count_langchain_messages([resp]),
                    },
                    goto='reflex'
                )
            return Command(
                update={
                    'messages': (resp, ),
                    'step': state.get('step',0)+1,
                    'thought': None,
                    # 'count': count_langchain_messages([resp]),
                },
                goto='thought'
            )



        def tool_node(state: State, config:RunnableConfig) -> Command[Literal['action','reflex','__end__']]:

            tool_calls = state['current_message'].tool_calls
            results = []
            chat_response = None
            
            # 验证和清理tool_calls格式
            if not tool_calls:
                logger.warning("tool_calls为空，跳过工具调用")
                return Command(
                    update={'messages': (state['current_message'],)},
                    goto='action'
                )
            
            # 如果tool_calls是字符串而不是列表，尝试解析
            if isinstance(tool_calls, str):
                logger.warning(f"tool_calls是字符串格式，尝试解析: {tool_calls[:100]}")
                # 尝试从字符串中提取工具调用
                # 这种情况不应该发生，但如果发生了，记录错误并跳过
                return Command(
                    update={'messages': (state['current_message'],)},
                    goto='action'
                )
            
            for tool_call in tool_calls:
                # 确保tool_call是字典格式
                if not isinstance(tool_call, dict):
                    logger.warning(f"tool_call格式不正确: {type(tool_call)}, 跳过")
                    continue
                
                tool_name = tool_call.get('name','')
                
                # 验证工具名是否有效
                if not tool_name:
                    logger.warning("tool_call缺少name字段，跳过")
                    continue
                
                # 清理tool_name，移除可能的特殊标记或格式错误
                original_tool_name = tool_name
                if tool_name not in self.TOOLS_MAP:
                    # 尝试从tool_name中提取实际的工具名
                    # 如果包含特殊标记，尝试提取
                    if '<tool_sep>' in tool_name or '<tool_call' in tool_name:
                        # 尝试提取第一个工具名
                        match = re.search(r'^([a-zA-Z_][a-zA-Z0-9_]*)', tool_name)
                        if match:
                            tool_name = match.group(1)
                            logger.info(f"从格式错误的tool_name中提取工具名: {original_tool_name[:50]} -> {tool_name}")
                        else:
                            logger.error(f"无法从tool_name中提取工具名: {tool_name[:100]}")
                            continue
                    else:
                        logger.error(f"未知的工具名: {tool_name}, 可用工具: {list(self.TOOLS_MAP.keys())}")
                        continue
                
                print(f'使用{tool_name}工具')
                args = tool_call.get('args',{})
                tool_call_id = tool_call.get('id',None)
                
                # 验证args格式
                if not isinstance(args, dict):
                    logger.warning(f"工具参数格式不正确: {type(args)}, 使用空字典")
                    args = {}
                
                tool = self.TOOLS_MAP[tool_name]
                response = tool.invoke(args)
                if tool_name =='chat':
                    chat_response = args.get('response',None)
                # LangChain/OpenAI 新版对 ToolMessage.content 有要求：
                # - 要么是 str，要么是带 {\"type\",\"text\"} 等字段的列表
                # 我们这里的工具（web_search、scan_page 等）多返回 dict/list，
                # 直接塞进去会触发你看到的 ValidatorIterator 错误，所以统一转成 JSON 文本。
                if tool_name == 'repl':
                    print(response)
                from json import dumps
                safe_content = dumps(response, ensure_ascii=False)
                results.append(ToolMessage(content=safe_content, tool_call_id=tool_call_id))
            return_tuple = tuple([state['current_message']] + results)

            if chat_response:

                return Command(
                    update={
                        'messages': return_tuple,
                        'response': chat_response,
                        # 'count': count_langchain_messages(results),
                    },
                    goto='__end__'
                )
            if state.get('step', 0)%100==0:
                return Command(

                    update={
                        'messages':return_tuple,
                        'current_message': None,
                        'step': state.get('step', 0)+1,
                        # 'count': count_langchain_messages(results),
                    },
                    goto='reflex'
                )
            return Command(
                update={
                    'messages': return_tuple,
                    'current_message': None,
                    'step': state.get('step', 0)+1,
                    # 'count': count_langchain_messages(results),
                },
                goto='thought'
            )


        def reflex_node(state: State, config: RunnableConfig)->Command[Literal['action', 'tool']]:


            state_ = {

            }
            system_prompt = get_template_by_name('reflex', state_)
            messages = []
            for t in state['messages']:
                for m in t:
                    messages.append(m)


            if self.prompt:
                messages = [HumanMessage(content=self.prompt)] + messages
            messages = [SystemMessage(content=system_prompt)] + messages



            messages += [AIMessage(content='我现在要反思一下')]

            llm_ = self.llm.bind_tools(self.tools, tool_choice='none')

            resp = llm_.invoke(messages)
            print(f'[{state["step"]}] [reflex]{resp.content}')
            resp.name = 'reflex'
            if len(resp.tool_calls) > 0:
                return Command(
                    update={
                        'current_message': resp,
                    },
                    goto='tool'
                )

            return Command(
                update={
                    'messages': (resp, ),
                    'step': state.get('step', 0)+1,
                    # 'count': count_langchain_messages([resp]),
                },
                goto='thought'
            )


        graph = StateGraph(State)
        graph.add_node('thought', thought_node)
        graph.add_node('action', action_node)
        graph.add_node('tool', tool_node)
        graph.add_node('reflex', reflex_node)
        graph.add_edge(START, 'thought')
        self.app = graph.compile()

        self.state = {
            'messages': (),
            'current_message': None,
            'step': 1,
            'response': None,
            'count': 0,
        }


    def invoke(self, **kwargs)-> State:
        input_messages = kwargs['input']
        config = kwargs['config']
        # count = count_langchain_messages(input_messages)

        self.state['messages'] += tuple(input_messages)
        self.state['count'] +=0


        resp = self.app.invoke(self.state,config=config)

        return resp


    def abstract(self, messages: List):
        system_prompt = get_template_by_name('abstract', {})
        messages  =[SystemMessage(content=system_prompt)]+messages
        resp = self.llm.invoke(messages)
        return [resp]


    def calculate_token(self, messages: List):

        results = []
        for message in messages:
            str_ = ''
            str_ += message.role
            str_ += message.content
            if message.role == 'assistant' and message.tool_calls:
                for tool_call in message.tool_calls:
                    str_ += tool_call.get('name','')
                    str_ += str(tool_call.get('args',{}))
                    str_ +=tool_call.get('id', '')
            results.append(str_)

    def export_openai_tool_schema(self, lc_tool: Any, name: str | None = None, description: str | None = None) -> dict:
        # 名称/描述
        t_name = name or getattr(lc_tool, "name", None) or getattr(lc_tool, "__name__", lc_tool.__class__.__name__)
        t_desc = (description
                  or getattr(lc_tool, "description", None)
                  or (inspect.getdoc(lc_tool) or "")
                  or f"Callable {t_name}")

        # 1) 优先：tool.args_schema（Pydantic 模型类）
        args_schema = getattr(lc_tool, "args_schema", None)
        if args_schema is not None:
            try:
                params = args_schema.model_json_schema()  # pydantic v2
            except Exception:
                params = args_schema.schema()  # pydantic v1
            params.setdefault("additionalProperties", False)
            return {"type": "function", "function": {"name": t_name, "description": t_desc, "parameters": params}}

        # 1.5) LangChain 通用：get_input_schema()（很多 BaseTool/StructuredTool 都支持）
        get_input_schema = getattr(lc_tool, "get_input_schema", None)
        if callable(get_input_schema):
            schema = get_input_schema()
            try:
                params = schema.model_json_schema()  # pydantic v2
            except Exception:
                params = schema.schema()  # pydantic v1
            params.setdefault("additionalProperties", False)
            return {"type": "function", "function": {"name": t_name, "description": t_desc, "parameters": params}}

        # 2) 从函数签名推断：优先 func，其次 _run（BaseTool 常见执行入口），最后别用 __call__（签名通常不对）
        func = getattr(lc_tool, "func", None) or getattr(lc_tool, "_run", None)
        if func is None:
            raise TypeError("无法从该 tool 取到 args_schema / get_input_schema / func/_run。")

        # === 下面保持你原来的 signature -> jsonschema 推断逻辑不变 ===
        from typing import get_type_hints, get_origin, get_args, Union, Literal, Any as TAny

        def pytype_to_jsonschema(tp: TAny) -> dict:
            origin, args = get_origin(tp), get_args(tp)
            if origin is Union and type(None) in args:
                sub = [a for a in args if a is not type(None)]
                return {"anyOf": [
                    {"anyOf": [pytype_to_jsonschema(a) for a in sub]} if len(sub) != 1 else pytype_to_jsonschema(
                        sub[0]),
                    {"type": "null"}]}
            if origin is Union:
                return {"anyOf": [pytype_to_jsonschema(a) for a in args]}
            if origin is Literal:
                return {"enum": list(args)}
            if origin in (list, tuple, set):
                return {"type": "array", "items": pytype_to_jsonschema(args[0] if args else TAny)}
            if origin in (dict,):
                v = args[1] if len(args) == 2 else TAny
                return {"type": "object", "additionalProperties": pytype_to_jsonschema(v)}
            if tp is str:   return {"type": "string"}
            if tp is int:   return {"type": "integer"}
            if tp is float: return {"type": "number"}
            if tp is bool:  return {"type": "boolean"}
            return {"type": "string"}

        sig = inspect.signature(func)
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}

        props, req = {}, []
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            schema = pytype_to_jsonschema(hints.get(pname, str))
            if p.default is inspect._empty:
                req.append(pname)
            else:
                try:
                    json.dumps(p.default)
                    schema["default"] = p.default
                except Exception:
                    pass
            props[pname] = schema

        parameters = {"type": "object", "properties": props, "required": req, "additionalProperties": False}
        return {"type": "function", "function": {"name": t_name, "description": t_desc, "parameters": parameters}}


def get_agent(name: str, llm: BaseChatModel, tools: List, prompt: str=None, enable_memory: bool=False)->BaseAgent:

    agent = BaseAgent(name=name, llm=llm, tools=tools, prompt=prompt)
    return agent


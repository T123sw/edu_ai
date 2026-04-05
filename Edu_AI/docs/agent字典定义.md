在 LangGraph 的概念下，开发这个“多模态AI互动式教学智能体”，本质上就是设计它的记忆中枢（State）、行为器官（Nodes）、决策神经（Edges）以及输出标准（Structured Output）。
以下为你完整梳理这四个核心部分的架构全貌：
一、 记忆中枢设计：全局状态字典 (Agent State)
这是智能体的“全局内存”。在多轮对话和任务流转中，智能体不会忘事，全靠这个状态字典来维系。你需要在这个字典中规划以下五大类“记忆槽位”：
1. 会话上下文 (Conversation Context)
  - 功能：记录教师与智能体之间的所有历史对话记录（包括文字、系统提示词，以及未来可能转录的语音文本）。这是智能体理解上下文的基础。
2. 路由控制状态 (Routing Status)
  - 功能：记录当前任务的核心走向。标明教师当前的意图是“日常答疑（Chat）”还是“生成课件（Generate）”，以防智能体在后续流程中迷失方向。
3. 教学设计蓝图 (Teaching Blueprint)
  - 功能：这是赛题要求的核心，也是智能体需要通过对话不断“填空”的区域。包含：教学目标、核心知识点、教学重点与难点、目标受众群体、互动设计思路（如动画、小游戏倾向）。
4. 多模态参考环境 (Multimodal Context)
  - 功能：记录教师在前端左侧面板勾选的外部知识源。存放被选中参考资料的标识（如 PDF 文件 ID、视频流的路径或关键帧描述关联），供 RAG 系统随时调取。
5. 工作流状态与产物 (Workflow & Artifacts)
  - 功能：存放智能体的“待办事项”和“劳动成果”。
    - 缺失项清单：记录教学蓝图中还差哪些信息没问清楚。
    - 课件草稿数据：存放智能体生成的结构化 PPT 数据（如包含页码、标题、排版结构的 JSON）以及 Word 教案文本，用于支持前端的预览和教师的局部修改。

---
二、 行为器官设计：核心功能节点 (Nodes)
节点是智能体执行具体动作的“职能部门”。根据赛题的闭环要求，你需要设计以下 6 个核心执行单元：
1. 意图路由分发器 (Router)
  - 职责：系统的大门保安。每次收到新消息时，负责分析这到底是一次闲聊提问，还是一个明确的生成任务指令，并为任务贴上对应的标签。
2. 日常答疑助手 (Chat QA)
  - 职责：处理非生成类的纯学术提问。结合知识库给出解答，不干扰课件生成的复杂流程。
3. 意图提取与解析器 (Intent Extractor)
  - 职责：在生成任务中充当“倾听者”。从教师的杂乱描述中，精准提炼出“教学蓝图”所需的各个要素（目标、难点、受众等），并将其放入对应的状态槽位中。
4. 状态评估与追问器 (Evaluator & Asker)
  - 职责：充当“需求审核员”。盘点“教学蓝图”是否已经填满。如果发现缺失（比如不知道讲给大几学生听），它会结合当前的语境，生成一句自然、得体的追问话术。
5. 多模态知识融合器 (Multimodal RAG Processor)
  - 职责：负责“读书看报”。当意图明确后，它负责去解析教师勾选的 PDF 和视频，提取出与当前教学蓝图匹配的专业知识、案例和排版风格。
6. 课件生成与修改引擎 (Generator & Modifier)
  - 职责：最核心的“打工人”。基于完备的教学蓝图和提取的多模态知识，生成结构化的 PPT 草稿和教案。如果收到教师的修改意见，它能精准定位到原草稿的特定部分（如第三页的案例），仅进行局部重写。

---
三、 决策神经设计：流转与控制逻辑 (Edges)
有了职能部门，还需要规定它们之间的业务流转规则，特别是在哪里需要**“挂起等待”**（人类在环）。
1. 入口分流规则
  - 用户发言后，首先进入“意图路由分发器”。如果判定为日常答疑，则走向“日常答疑助手”，完成后结束本轮；如果判定为生成任务，则走向“意图提取与解析器”。
2. 循环追问规则 (核心闭环 1)
  - 信息提取后，流入“状态评估与追问器”。
  - 条件判断：如果蓝图不完整 ➡️ 发送追问话术给前端 ➡️ 图运行结束（休眠）。等待教师回复后，唤醒图再次进入提取器，形成直到问清为止的循环。
  - 条件判断：如果蓝图已完整 ➡️ 放行，流入“多模态知识融合器”。
3. 人类在环与修改规则 (核心闭环 2)
  - 知识融合并由“生成引擎”产出初稿后 ➡️ 触发硬性中断（挂起）。此时将结果推送给前端预览。
  - 等待交互：图在此处休眠。如果接收到前端传来的修改意见，图被唤醒并流回“修改引擎”进行局部重写，完成后再次挂起。如果接收到确认导出的指令，则结束图运行，触发文件下载。

---
四、 沟通标准设计：结构化输出模版 (Structured Outputs)
为了让智能体的大脑（DeepSeek 模型）稳定可控，你不能让它随性发挥，必须为关键节点制定严格的“输出填表模板”（底层基于 Tool Calling / JSON Mode）。
1. 路由决策表
  - 强制大模型只输出两个选项之一：chat 或 generate。杜绝任何寒暄废话。
2. 意图信息收集表
  - 强制大模型以固定的格式输出提取到的要素，例如明确的数组格式存放“核心知识点”，字符串格式存放“受众目标”。如果没有提取到，必须严格留空，不能自行编造。
3. PPT 结构化数据表
  - 这是最复杂的表单。强制大模型按页输出：每页必须包含“页面类型（封面/目录/内容）”、“主标题”、“要点列表”、“配图建议”、“演讲者备注”等规定字段。只有输出这样严谨的格式，前端才能完美渲染预览，修改引擎才能精准定位局部节点。
理清了这四个维度的抽象架构，你接下来无论用什么语言写代码，都只是把这些“业务语言”翻译成“机器语言”的过程。系统整体的健壮性和逻辑闭环已经完全建立起来了！


这是一个非常经典且高效的架构设计！在 Agent 领域，这被称为 “路由模式”（Router Pattern） 或 “监督者模式”（Supervisor Pattern）。
将 Agent 设计成一个“交通警察”，让它在入口处先判断用户的意图，然后再把任务分发给不同的“专员”（普通的对话节点 vs. 复杂的生成工具节点），不仅能大幅提高响应速度，还能避免大模型在不需要调用工具的时候“胡乱调用”。
为了实现这个设计，我们需要对之前规划的 LangGraph 架构进行升级，在最前端增加一个 路由节点（Router Node）。
以下是具体的实现方案：
一、 升级“状态字典” (State Schema)
我们需要在 State 中增加专门用于记录“路由决策”的字段：
Python
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages

class TeachingAgentState(TypedDict):
    messages: Annotated[list, add_messages] 
    reference_materials: List[str] 
    
    # === 新增：路由决策状态 ===# 记录用户的核心意图类别：'chat'(纯对话/咨询), 'generate_content'(要求生成课件/报告等)
    intent_category: Optional[str] 
    
    # === 教学意图结构化特征 (保持不变) ===
    teaching_target: Optional[str]      
    core_knowledge: Optional[List[str]] 
    missing_info: List[str]             
二、 重新设计图的节点 (Nodes) 与职责
现在的系统需要三类节点：
1. 入口路由节点 (router_node)：
  - 职责：充当大脑的“前额叶”。每次收到新消息时，它只做一件事：判断用户是在聊天问问题，还是下达了生成任务的指令。
  - 输出：更新 State 中的 intent_category 为 'chat' 或 'generate_content'。
2. 普通对话/答疑节点 (chat_node)：
  - 职责：处理普通的问答。例如用户问“TCP协议是什么？”，它会结合本地 RAG 知识库（左侧面板选中的文件）给出解答，不触发复杂的生成逻辑。
3. 生成意图梳理节点群 (tool_preparation_nodes)：
  - 职责：处理生成任务。这就衔接到了我们上一步设计的逻辑（提取教学目标、追问缺失信息）。例如用户说“帮我生成一份关于TCP协议的报告”，它会接管流程，检查生成报告需要的参数够不够，不够就反问。
三、 设定条件边 (Conditional Edges)：画出分流逻辑
这是 LangGraph 最迷人的地方，我们用条件边来实现动态路由：
1. 起点 (START) ➡️ 指向 router_node。
2. router_node 之后的条件分支 (Conditional Edge)：
  - 检查 intent_category。
  - 如果是 'chat' ➡️ 流向 chat_node。
  - 如果是 'generate_content' ➡️ 流向意图提取与追问节点（我们上一阶段设计的逻辑）。
3. 终点 (END)：无论是 chat_node 还是追问节点处理完，都流向 END，把结果返回给前端。
四、 Router 节点的 System Prompt 设计 (核心)
路由节点准不准，全靠提示词。你需要给 router_node 配置类似这样的 Prompt：
"你是一个智能教学助手的意图识别路由引擎。请分析用户的最新输入并进行分类。
分类选项：
1. chat: 用户只是在提问、探讨学术问题、寻求解答或进行日常交流。
2. generate_content: 用户明确要求生成具体的教学材料，包括：报告、PPT课件、思维导图、教案、测验题或闪卡。
注意：如果用户只是问'如何写教案'，分类为 chat；如果用户说'帮我生成一份关于数据结构的教案'，分类为 generate_content。
请严格以 JSON 格式输出你的分类结果，字段名为 intent_category。"

---
下一步建议
采用这种“路由模式”，你的系统架构会变得极其清晰，且具有极强的可扩展性（未来如果你增加了“数据采集”的 Agent，只需在路由里加一个分支即可）。
接下来，针对这个极其关键的 Router 节点 (router_node)，你打算如何让大模型输出标准化的路由结果？
- 选项 A：使用 OpenAI 或类似支持 Function Calling / Tool Calling 的模型，让它“调用一个叫 route_request 的假工具”来返回结构化数据。
- 选项 B：使用普通大模型，通过 Prompt 强迫它输出 JSON 字符串，然后我们在 Python 代码里手动 json.loads() 解析它。
你更倾向于哪种方式？


设计后端的 LangGraph 状态（State）和节点流转，是整个智能体开发中最核心、也是最有趣的一步。这就好比你在为这位“数字教学专家”设计它的记忆中枢和思维回路。
根据赛题要求，智能体需要通过对话，提取出教师的教学目标、核心知识点、重点难点等信息 ()。我们需要将这些要求结构化。
以下是为你梳理的 LangGraph “状态字典”与流转逻辑设计方案：
一、 梳理并定义“状态字典” (State Schema)
在 LangGraph（Python 环境）中，State 通常是一个 TypedDict 或 Pydantic 模型。它在每一次多轮对话中都会被传递和更新。针对你的意图澄清阶段，我们需要定义三大类状态：
Python
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages

class TeachingAgentState(TypedDict):# ==========================================# 1. 对话记忆 (Memory)# ==========================================# 存储所有的对话历史（用户输入、AI回复、Tool的调用结果）# Annotated[..., add_messages] 告诉 LangGraph 不要覆盖，而是追加消息
    messages: Annotated[list, add_messages] 
    
    # 用户在前端左侧面板勾选的参考资料列表（如 PDF、视频的 ID 或路径）[cite: 432]
    reference_materials: List[str] 

    # ==========================================# 2. 教学意图结构化特征 (Extracted Intents) # ==========================================# 这些是我们需要通过对话慢慢“填满”的槽位
    teaching_target: Optional[str]      # 教学目标 (如：掌握TCP三次握手)
    core_knowledge: Optional[List[str]] # 核心知识点 (如：[SYN, ACK, 序列号])
    key_difficulties: Optional[str]     # 重点难点 
    interaction_ideas: Optional[str]    # 互动设计思路 (如：用动画演示)
    target_audience: Optional[str]      # 目标受众 (如：计算机大二学生)# ==========================================# 3. 智能体控制状态 (Control Status)# ==========================================# 记录当前还缺失哪些必填信息，用于指导 Agent 提问
    missing_info: List[str]             
    # 当前流程状态：'clarifying'(澄清中) -> 'summarizing'(总结待确认) -> 'ready'(可生成课件)
    phase: str                          
二、 设计图的节点 (Nodes)
节点是执行具体动作的函数。在“对话与意图澄清”阶段，我们不需要太复杂的网状结构，只需设计以下 3 个核心节点：
- Node 1: 意图提取器 (extract_intent_node)
  - 职责：大模型充当“倾听者”。它读取最新的 messages，并尝试从中提取 teaching_target、core_knowledge 等字段。如果提取到了，就更新到 State 中。
  - 机制：使用大模型的**结构化输出（Structured Output）**功能，让大模型强制返回 JSON 格式的提取结果。
- Node 2: 状态评估器 (evaluate_completeness_node)
  - 职责：一个简单的 Python 逻辑节点（不调用大模型）。检查 State 中的必填项是否都已填满。
  - 机制：如果 teaching_target 或 core_knowledge 为空，就把缺失项写入 missing_info 列表。
- Node 3: 对话生成器 (generate_response_node)
  - 职责：大模型充当“沟通者”。
  - 机制：
    - 如果 missing_info 不为空，大模型根据缺失列表，生成一句自然、礼貌的追问（例如：“老师，您这节课的核心知识点我已经清楚了，那您希望在课堂上设计哪些互动环节呢？”）。
    - 如果 missing_info 为空，大模型生成一段完整的总结，并询问教师是否确认无误（例如：“老师，总结一下您的需求：... 是否确认开始生成课件？”），并将 phase 改为 summarizing。
三、 设计状态流转逻辑 (Edges)
有了节点，我们需要用边（Edges）把它们连起来，形成一个闭环的思维流：
1. 用户在前端发送消息 ➡️ 触发图的起点 (START)。
2. START 无条件流向 ➡️ extract_intent_node (尝试提取最新意图)。
3. extract_intent_node 无条件流向 ➡️ evaluate_completeness_node (检查填槽进度)。
4. evaluate_completeness_node 无条件流向 ➡️ generate_response_node (生成回复)。
5. generate_response_node ➡️ 触发图的终点 (END)，将生成的回复通过 API 推送回前端的 React ChatPanel 中，等待用户的下一次回复。

---
下一步操作建议：
以上就是后端的骨架设计。这套逻辑能保证你的智能体绝对不会像普通的 ChatGPT 那样“盲目接话”，而是会像一个真正的产品经理一样，有目的地引导教师提供完备的生成条件。
为了把这个骨架变成真正的代码，我们需要决定 Node 1（意图提取） 的实现方式。你会更倾向于使用哪种大模型 API？
1. OpenAI / 阿里通义千问 API（原生支持极好的 response_format={"type": "json_schema"} 结构化输出能力，代码最简洁）。
2. 本地/其他开源模型（需要使用 LangChain 的 PydanticOutputParser 来手动解析提示词）。
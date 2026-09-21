# 共享参数与交接契约 v1.1

2026-09-21 集成澄清：`teaching_context.requirements` 保留整课原要求，`requirement_ids` 是已审路径分配给当前节点的要求。每份资源只声明有真实位置的落实映射，不能要求它重复教授其他节点内容。D/E 校验每条映射真实性，F 在创建/调整课程时汇总本节点全部资源，强制覆盖该节点要求，缺口进入有界修复；提交前再次检查。旧不含节点分工的上下文继续使用原逐资源覆盖检查。消费者 D/E/F 已同步，A 规格和原始摘要不变。

习题可追加逐题 `question_time_estimates`（question_id、thinking_seconds、reason），D 汇总思考/作答估计并加上题干/选项/解析阅读估计。仍标 estimated，并明确非实测、未经学习者校准；缺失则 unknown，F 不放行硬时限。资源正文修订后重新审阅估算及语义。没有单独资源清单规划或新用户操作。

本文件是 A–G 的共同接口约定，不是当前代码已具备的功能。范围和优先级见[总计划](../2026-09-19-preparation-chain-optimization.md)。新符号必须由指定负责人实现后才能用于主流程；变更此约定时同步列明全部消费者。

## 1. 必须保留的流程与事实来源

```text
request + uploads + effective memory
  → normalize / ingest
  → research_scope / plan / research_nodes
  → 现有 resource_specs 构建（不新增阶段）
  → produce（报告、习题、已要求的课堂）
  → review → 必要的 repair → commit
  → manifest / exact resource versions → 学习端
```

SQL 检查点是进度事实，原生 Harness 是智能决策执行内核，工具执行回执是外部动作事实；模型文字不是这些事实的替代品。上传资料/网页不是操作指令；记忆不是知识证据或掌握事实。

## 2. 参数语义表

| 信息 | 权威来源 | 消费者 | 必须验证的实际效果 |
| --- | --- | --- | --- |
| 用户目标/排除项/来源限制 | 原始 request＋带出处的 brief | C/D/E/F | 不降低目标、不引入排除主题、不越权联网 |
| 基础与预期能力 | 用户明确输入/授权背景；缺失注明未知或假设 | D/E/F | 解释深度与例子前提适配；不把偏好当掌握 |
| 教学顺序与其他本次要求 | 原始要求及 requirement_id | D/E/F | 产物章节/场景中的实际顺序可定位 |
| 有效偏好 | memory_view.preferences 的值、来源与 revision | A/D/E/F | 影响表达；与本次要求冲突时服从本次要求；删除后派生上下文失效 |
| 节点目标/先修/活动/自测 | 已审阅 plan 的对应节点 | A/D/E/F | 生成与检查使用本节点信息，不能退回固定模板 |
| node_budget_minutes | plan.nodes[].minutes | D/E/F | 这是整节点的学习时间约束，不是每份资源的独立时长 |
| resource_target_minutes | 仅明确约束或既有可验证值；默认 null | D/E/F | null 表示没有单资源时间分配，不自动复制节点上限 |
| 实际/估算用时 | 生成内容结构、音频实际时长、明确估算规则 | E/F/G | 区分 estimated/measured，不能从页数直接声称真实学习时长 |
| 需求、目标、结论和来源 ID | 上游持久化对象 | 全部 | ID 可解引用；引用真实原文；不得用 ID 齐全冒充语义覆盖 |
| config_snapshot | 服务端解析的运行配置版本 | B/C/E/F | 任务中一致使用；密钥不进入上下文或回执 |
| memory_refs/epoch、基准版本、owner、deadline | 服务端 | B/C/F | 改变后触发相应失效/冲突；模型不能自行提供新授权 |

## 3. A 提供的教学上下文

拟新增 `backend/src/app/course_preparation/teaching_context.py`；类型/函数由 A 独占。其公开签名：

```python
def build_teaching_context(*, request: PreparationRequest,
                          checkpoint: dict, node: dict) -> TeachingContext: ...

# backend/src/app/course_preparation/generation_context.py
def automatic_payload(spec: dict, artifact: dict) -> SimpleNamespace: ...
```

`TeachingContext` 使用 Pydantic 严格 schema，至少含以下字段；下游读取同一对象，不能再从拼接的 focus 字符串反解析：

```text
schema_version: 1
request_goal: str                         # 原始本次目标
requirements: list[RequirementContext]    # requirement_id、text、source_quote、source_document_id
prior_knowledge: str                      # 空值表示未知，不臆测
desired_outcomes: list[str]
exclusions: list[str]
language: str
depth: str | null
source_policy: dict                      # 执行约束仍由服务端校验
effective_preferences: dict              # 白名单偏好值，保留来源/revision
node_id: str
objective_ids: list[str]
objectives: list[str]
prerequisites: list[NodeReference]         # node_id、title、objectives
learning_activities: list[str]
self_check: str
node_budget_minutes: int
resource_target_minutes: int | null
assumptions: list[str]
limitations: list[str]                    # 路径/来源真实限制，非免责替代核心目标
```

`RequirementContext` 保留原要求出处，`NodeReference` 只允许引用本路径中真实先修。旧 brief 使用 `requirement_id`，适配时不改其身份。完整原始 request 仍由服务端保存，不把整段聊天或无关记忆扩充进此对象。

新增资源规格使用 `schema_version=2` 和必需的 `teaching_context`。旧规格缺 schema_version 时按 v1 读取；不能因 Pydantic 默认字段而重算旧持久化 spec_digest、改变幂等键或复用错误草稿。既有 `minutes` 在 v2 中保留兼容读取且必须等于 node_budget_minutes，新写作逻辑只能把它当节点约束。

`automatic_payload()` 提供 `teaching_context`、结构化 evidence、原文研究 context、修改基线、资源类型及服务端执行上下文；不再填固定面试大纲。保留旧调用位置的兼容 wrapper，由 B 在 `adapters/generation.py` 实现。D/E 用规范化上下文构造自己的内容结构，不新增独立清单规划阶段。

## 4. B 提供的有阶段语义的 Harness 网关

拟新增 `harness_generation.py`。保持既有生成器 `chat()` 的接口，增加显式阶段绑定；不能靠解析中文提示词猜阶段。

```python
class PreparationHarnessGateway:
    def for_phase(self, phase: str, *, context: dict) -> 'PreparationHarnessGateway': ...
    def chat(self, messages: list[dict], temperature: float = .2,
             max_tokens: int = 12000) -> str: ...

def scoped_gateway(gateway, *, phase: str, context: dict,
                   preparation: bool): ...
```

`scoped_gateway()` 在 preparation=true 时要求原生 Harness 能力，缺失返回明确配置/运行失败，不静默直连；preparation=false 时保持旧工作台兼容。绑定返回新视图，不能跨并发子任务修改同一 gateway.phase。

| phase | Skill 名称（拟新增） | 负责人 |
| --- | --- | --- |
| resource_write / resource_repair | generate-learning-resource | D |
| resource_review | review-learning-resource | D |
| classroom_write / classroom_repair | generate-ai-classroom | E |
| course_review | review-course-delivery | F |

课堂内容审阅复用 resource_review；写作与审阅必须独立输入/会话，不能把写作者的“通过”当审阅结果。B 负责统一注册和角色路由，D/E/F 负责 Skill 正文和业务校验。

SDK 使用受限提交工具交回正文/JSON 字符串，D/E 的原生 schema 和内容校验随后执行。不能让一个 Harness 工具内部偷偷使用直连模型完成全部写作。每个真实 completion 必须有 runtime、phase、skill.name、skill.sha256、skill.loaded、provider/model、真实 usage、上游规格摘要。业务 result 回读失败不得标完成。

## 5. 资源验收和故障契约

本轮不重设计全平台资源 schema。D/E 在既有 artifact / generation_state 下追加版本化、可回读的元数据，由 F 校验：

```text
generation_state.preparation:
  schema_version: 1
  spec_digest: str
  teaching_context_digest: str
  applied_requirements: [{requirement_id, locator, explanation}]
  objective_bindings: [{objective_id, locator, role}]
  duration: {value_minutes: number|null, basis: estimated|measured|unknown, method: str}
```

`locator` 为现有原生资源中的稳定定位对象：报告 section_id、习题 question_id、课堂 scene_id/action_id。`role` 为 explanation/practice/check。生成器提供的是候选映射，F 要验证位置存在并审阅是否真的支持目标，不能照抄为可信事实。目标 ID 不得指向其他节点；内容变更使摘要绑定的审阅和估算失效。无法可靠估算时明确 unknown，不生成假精度。

F 拟新增 `generation_failures.py`，提供统一 `GenerationFailure`（异常）和 `FailureDetail`（schema）：

```text
code: str
phase: str
category: provider|review_format|content|render|contract|permission|budget|canceled
message: str                              # 脱敏、具体原因
retry_scope: none|provider|review|content
artifact_id: str|null
content_digest: str|null
```

D/E 抛出具体错误，B 在 generation handler 保留 detail，F 决定是否重试及其范围。不能把所有失败统一改成 RESOURCE_GENERATION_FAILED；也不能依靠重写异常 message 推断恢复动作。

为支持不重写正文的审阅恢复，F 提供 `ResourceCheckpointPort`：

```python
class ResourceCheckpointPort:
    def load_review_candidate(self) -> dict | None: ...
    def save_review_candidate(self, *, content: dict | str, content_digest: str,
                              spec_digest: str, review_state: dict) -> None: ...
```

B 以服务端已授权的 artifact 身份构造端口，作为 `checkpoint=` 参数传给 D/E 的生成器；它不是可序列化模型参数，不进入 prompt。D 的 `generate_reviewed_report`、`ReviewedResourceGenerator` 构造器、`review_classroom`，以及 E 的 `generate_classroom_draft` 均新增可选 `checkpoint=None`，保持旧入口兼容。准备主流程启用此端口，保存的是尚未通过审阅的私有候选；不能把它标为 ready/draft 或挂到课程上。

只有元数据字段不足而正文有效时保留正文、修补相关结果；只有正文有错误才更新正文。任何终端写入都复核 owner、attempt、lease、预算、取消、记忆引用和目标版本。异常回执不得泄露凭据。

## 6. 参数确实生效的验收方法

每个窗口提交参数追踪记录：`input_path → validated_value → consumer → artifact_locator → check_result`。下列是语义断言，不要求 LLM 输出逐字一致：

1. 相同主题，分别要求“先例子再原理”和“先原理再例子”：最终章节/场景顺序应相应变化；仅 prompt 不同不算通过。
2. 空记忆可运行；非空偏好影响内容；本次相反要求优先；删除偏好使相关旧结果不可继续交付。
3. 节点先修、活动、自测能在生成上下文中回读且在资源或检查中定位；目标与题目引用真实对应。
4. 只上传且材料不足，应明确失败；不能改为伪代码后称目标全部达成。
5. review_format 故障恢复时正文 digest 保持不变；content 故障修复后正文 digest 改变且重新审阅。
6. 篡改 spec/context/content 任一摘要，旧通过回执不能用于 commit。

本契约是阶段间最小一致性约定；未来独立资源规划可复用它，但本轮不能借此新增资源组合决策或新的用户操作步骤。

# 教师端（Teacher Studio）重构设计方案

## 一、架构总览

### 1.1 设计哲学
教师端重构的核心是**"杠杆效应"**——最大化教师单位时间的产出价值。将教师从"出题机器"转变为"知识策展人"，通过AI工具降低备课负担，提升教学质量。

### 1.2 核心设计理念：统一的模型交互界面

**核心思想**：教师和学生在**同一个界面**与AI模型进行交互，该界面采用NotebookLM风格的三栏布局：
- **左侧栏（Source Panel）**：知识库管理、文档导入、深度研究
- **中间栏（Chat Panel）**：与AI模型对话交互
- **右侧栏（Studio Panel）**：生成式工场（习题、博客、教案、音频等）

**功能分离原则**：
- **模型交互界面**：所有与AI模型直接交互的功能（知识库导入、深度研究、内容生成、对话）
- **独立管理页面**：需要复杂UI的功能（知识图谱可视化编辑、学情分析仪表盘等）

### 1.3 功能模块划分

```
教师端（Teacher Studio）
├── 1. 模型交互界面（统一界面，NotebookLM风格）
│   ├── 左侧栏：知识库管理 (Source Panel)
│   │   ├── 文档上传/导入
│   │   ├── 网页深度研究
│   │   ├── 文档列表管理
│   │   └── 知识库选择（用于RAG检索）
│   │
│   ├── 中间栏：对话交互 (Chat Panel)
│   │   ├── 与AI模型对话
│   │   ├── 基于选中知识库的RAG检索
│   │   ├── 消息历史管理
│   │   └── 引用溯源显示
│   │
│   └── 右侧栏：生成式工场 (Studio Panel)
│       ├── 生成习题（基于对话上下文）
│       ├── 生成博客
│       ├── 生成教案
│       ├── 生成音频概览
│       └── 生成知识导图
│
├── 2. 知识库管理页面（独立页面）
│   ├── 知识图谱可视化编辑器
│   ├── 深度摄取配置
│   └── 文档高级管理
│
└── 3. 学情分析仪表盘（独立页面）
    ├── 知识图谱热力图
    ├── 概念掌握度分析
    └── 交互深度分析
```

## 二、详细功能设计

### 2.1 统一模型交互界面（核心界面）

#### 2.1.1 左侧栏：知识库管理 (Source Panel)

**功能目标**：
- 在统一界面中管理知识库来源
- 支持文档上传和网页深度研究
- 支持多文档选择和切换

**界面设计**（基于现有 `SourcePanel.tsx` 扩展）：
```typescript
// 现有功能
- 文档列表显示
- 文档选择（Checkbox）
- 文档上传按钮

// 需要扩展的功能
- 网页深度研究入口（集成到"添加来源"按钮的下拉菜单）
- 文档上传进度显示（上传中的文档显示进度条）
- 文档预览功能（点击文档查看摘要）
- 文档删除和编辑
```

**核心功能扩展**：

1. **文档上传增强**：
   - 支持拖拽上传
   - 实时上传进度显示
   - 上传完成后自动解析（后端异步处理）
   - 解析完成后更新文档状态

2. **网页深度研究集成**：
   - 在"添加来源"按钮旁添加"深度研究"按钮
   - 点击后弹出搜索框，输入研究主题
   - 启动深度研究智能体（后端异步任务）
   - 研究完成后自动添加到文档列表

**后端API**:
```
POST /teacher/sources/upload
  - 文件上传接口
  - 返回文档ID和上传任务ID

GET /teacher/sources/upload/{task_id}
  - 查询上传和解析进度

POST /teacher/sources/research
  - 启动深度研究任务
  - 输入：研究主题、白名单站点（可选）
  - 输出：任务ID

GET /teacher/sources/research/{task_id}
  - 查询研究进度和结果

POST /teacher/sources/research/{task_id}/confirm
  - 确认研究结果，添加到知识库
```

#### 2.1.2 中间栏：对话交互 (Chat Panel)

**功能目标**：
- 基于选中的知识库进行RAG检索
- 支持多轮对话
- 显示引用来源

**界面设计**（基于现有 `ChatPanel.tsx` 扩展）：
```typescript
// 现有功能
- 消息列表显示
- 消息输入框
- 发送按钮

// 需要扩展的功能
- 引用来源显示（在每个AI回复后显示来源列表）
- 模型选择器（支持切换不同模型）
- RAG开关（可以选择是否使用RAG检索）
- 对话历史管理（侧边栏或下拉菜单）
- 消息编辑和重新生成
```

**核心功能扩展**：

1. **RAG检索增强**：
   - 自动使用左侧栏选中的文档进行检索
   - 在AI回复下方显示引用来源卡片
   - 点击来源可跳转到原文

2. **对话上下文管理**：
   - 支持创建新对话
   - 支持切换对话历史
   - 支持删除对话

3. **消息操作**：
   - 编辑用户消息并重新发送
   - 重新生成AI回复
   - 复制消息内容

**后端API**（大部分已存在，需要确认）:
```
POST /api/chat
  - 发送消息，基于选中的文档进行RAG检索

GET /api/conversations
  - 获取对话列表

GET /api/conversations/{conversation_id}
  - 获取对话历史

DELETE /api/conversations/{conversation_id}
  - 删除对话
```

#### 2.1.3 右侧栏：生成式工场 (Studio Panel)

**功能目标**：
- 基于对话上下文和选中知识库生成各类教学资源
- 生成的内容统一在右侧栏管理和预览

**界面设计**（基于现有 `StudioPanel.tsx` 扩展）：
```typescript
// 现有功能
- 生成按钮（报告、测验、知识导图）
- 生成文件列表
- 文件预览

// 需要扩展的功能
- 生成按钮扩展：习题、博客、教案、音频
- 生成配置面板（点击生成按钮后弹出）
- 生成进度显示（异步任务进度）
- 生成内容预览和编辑
- 生成内容导出（Markdown、PDF等）
```

**核心功能扩展**：

1. **生成按钮扩展**：
   ```typescript
   - 生成报告（Summary Report）
   - 生成习题（Quiz/Assessment）
   - 生成博客（Blog Post）
   - 生成教案（Lesson Plan）
   - 生成音频概览（Audio Overview）
   - 生成知识导图（Knowledge Graph）
   ```

2. **生成配置**：
   - 每个生成类型都有配置选项
   - 例如：生成习题时可以配置难度、题型、数量
   - 例如：生成音频时可以配置角色风格、时长

3. **生成流程**：
   - 点击生成按钮 → 弹出配置面板
   - 填写配置 → 确认生成
   - 显示生成进度（异步任务）
   - 生成完成后在文件列表中显示
   - 点击文件进行预览和编辑

**后端API**:
```
POST /teacher/studio/generate
  - 统一生成接口
  - 输入：生成类型、配置参数、上下文（对话ID、选中文档）
  - 输出：任务ID

GET /teacher/studio/task/{task_id}
  - 查询生成进度和结果

GET /teacher/studio/content/{content_id}
  - 获取生成内容的详细信息

PUT /teacher/studio/content/{content_id}
  - 更新生成内容（支持编辑）

DELETE /teacher/studio/content/{content_id}
  - 删除生成内容

POST /teacher/studio/content/{content_id}/export
  - 导出生成内容（支持多种格式）
```

### 2.2 知识库管理页面（独立页面）

**功能目标**：
- 提供高级的知识库管理功能
- 知识图谱的可视化编辑
- 深度摄取配置

**界面设计**：
```typescript
KnowledgeBasePage.tsx
  - 知识图谱可视化编辑器（使用@antv/g6）
  - 文档高级管理（批量操作、标签管理）
  - 深度摄取配置面板
```

**核心功能**：
1. 知识图谱可视化编辑
2. 文档元数据批量编辑
3. 切片策略配置
4. 图谱导出

**后端API**（与模型交互界面共享部分API）:
```
GET /teacher/knowledge-base/graph
PUT /teacher/knowledge-base/graph/{node_id}
POST /teacher/knowledge-base/graph/export
```

### 2.3 生成式工场详细设计（右侧栏功能）

#### 2.3.1 生成类型定义

所有生成功能都集成在右侧栏的Studio Panel中，包括：

1. **生成报告（Summary Report）**
   - 基于选中文档或对话上下文生成摘要报告
   - 配置：报告长度、重点内容

2. **生成习题（Quiz/Assessment）**
   - 基于对话上下文和知识点生成题目
   - 配置：题型、难度、数量、误解分析
   - 输出：选择题、填空题、简答题

3. **生成博客（Blog Post）**
   - 将教学内容转化为教学博客
   - 配置：风格、长度、目标受众

4. **生成教案（Lesson Plan）**
   - 基于知识点和教学目标生成教案
   - 配置：课时长度、难度、重点难点

5. **生成音频概览（Audio Overview）**
   - 将教材章节转化为双人对话播客
   - 配置：角色风格、时长、章节选择
   - 工作流程：
     1. 选择章节（从左侧栏选中的文档）
     2. 配置角色（Host A: 专家型, Host B: 好奇型）
     3. 生成脚本（JSON格式对话脚本）
     4. TTS音频合成（OpenAI TTS / ElevenLabs）
     5. 后期混音（可选背景音乐）
     6. 生成时间戳索引

6. **生成知识导图（Knowledge Graph）**
   - 基于文档内容自动提取概念并构建导图
   - 配置：概念提取深度、关联度阈值

#### 2.3.2 生成配置面板设计

```typescript
interface GenerateConfigPanel {
  // 通用配置
  type: 'report' | 'quiz' | 'blog' | 'lesson_plan' | 'audio' | 'graph';
  contextSource: 'conversation' | 'documents'; // 基于对话还是文档
  contextId?: string; // 对话ID或文档ID列表
  
  // 生成类型特定配置
  config: 
    | ReportConfig 
    | QuizConfig 
    | BlogConfig 
    | LessonPlanConfig 
    | AudioConfig 
    | GraphConfig;
}

// 示例：习题生成配置
interface QuizConfig {
  knowledgePoints: string[]; // 知识点
  types: ('choice' | 'blank' | 'short')[]; // 题型
  difficulty: 'low' | 'medium' | 'high';
  count: number;
  useMisconceptionAnalysis: boolean; // 是否使用误解分析
}
```

#### 2.3.3 生成内容管理

所有生成的内容统一在Studio Panel的文件列表中管理：
- 文件列表显示（按类型分组）
- 点击文件进行预览
- 支持编辑和导出
- 支持删除

#### 2.3.4 技术实现细节

**深度研究智能体**（集成到左侧栏）：
- 工作流程：
  1. 规划（Planning）：将任务拆解为搜索关键词
  2. 执行（Execution）：调用Tavily/Google Search API
  3. 清洗与合成（Scraping & Synthesis）：使用Firecrawl抓取并生成简报
  4. 审核（Review）：教师审核后入库
- 技术栈：LangGraph、Tavily、Firecrawl

**音频概览生成**：
- 工作流程：
  1. 脚本生成（Script Writer）：生成JSON格式对话脚本
  2. 音频合成（TTS Engine）：调用TTS API
  3. 后期混音：添加背景音乐（可选）
  4. 存储与发布：存入对象存储，生成时间戳索引
- 技术栈：OpenAI TTS / ElevenLabs

**智能考题生成**：
- 生成策略：
  1. 检索"初学者常犯错误库"
  2. 基于误解类型生成干扰项
  3. Critic模型审核（检查逻辑漏洞）
  4. 生成答案和解析

### 2.4 学情分析仪表盘（独立页面）

#### 2.3.1 知识图谱热力图

**功能目标**：
- 可视化展示班级对各知识点的掌握度
- 节点颜色 = 掌握度（红=低，绿=高）
- 关联分析：发现知识点间的关联问题

**数据来源**：
- 学生答题数据
- AI辅导中的提问数据
- 音频播放的暂停点数据

**界面设计** (`AnalyticsDashboardPage.tsx` - 独立页面):
```typescript
- 使用与知识图谱相同的可视化组件
- 节点颜色动态映射到掌握度
- 点击节点查看详细数据
- 筛选功能（按时间、班级等）
```

**后端API**:
```
GET /teacher/analytics/concept-mastery
  - 返回各知识点的掌握度数据
  - 支持时间范围筛选

GET /teacher/analytics/concept-correlations
  - 返回知识点间的关联分析
  - 识别"理解定义但不会应用"的情况
```

#### 2.3.2 交互深度分析

**功能目标**：
- 分析学生在音频中的暂停点
- 识别普遍理解障碍
- 生成干预建议

**后端API**:
```
GET /teacher/analytics/audio-interactions
  - 返回音频播放的暂停点统计
  - 按时间戳聚合暂停次数

GET /teacher/analytics/intervention-suggestions
  - 基于分析结果生成干预建议
  - 例如："为'建模'概念生成新音频概览"
```

## 三、技术架构调整

### 3.1 前端架构

**核心界面结构**（基于现有的frontend项目）:
```
frontend/src/
├── components/
│   ├── SourcePanel.tsx        # 左侧栏：知识库管理（需扩展）
│   ├── ChatPanel.tsx          # 中间栏：对话交互（需扩展）
│   └── StudioPanel.tsx        # 右侧栏：生成式工场（需扩展）
│
├── pages/
│   └── ModelInteractionPage.tsx  # 主页面（整合三栏布局）
│
└── services/
    └── api.ts                 # API服务（需扩展）
```

**独立管理页面**（在Edu_AI/src/pages中）:
```
src/pages/
├── teacher/
│   ├── KnowledgeBasePage.tsx      # 知识库高级管理（知识图谱编辑）
│   ├── AnalyticsDashboardPage.tsx # 学情分析仪表盘
│   └── TeacherToolsPage.tsx       # 其他教师工具（如需保留）
│
└── student/  (未来学生端目录)
    └── ...
```

**组件复用**:
- 音频播放器组件（Studio Panel预览 + 学生学习）
- 知识图谱可视化组件（独立页面编辑 + 学生学习路径）
- 消息组件（Chat Panel复用）

### 3.2 后端架构

**API路由设计**:
```
# 模型交互界面相关API
/api/chat                          # 对话接口（已存在，需确认）
/api/conversations                 # 对话管理（需新增）
/api/conversations/{id}            # 对话历史（需新增）

# 知识库管理（Source Panel）
POST /teacher/sources/upload       # 文档上传
GET  /teacher/sources/upload/{task_id}  # 上传进度
POST /teacher/sources/research     # 启动深度研究
GET  /teacher/sources/research/{task_id}  # 研究进度
POST /teacher/sources/research/{task_id}/confirm  # 确认入库
GET  /teacher/sources/list         # 文档列表（可能已存在）

# 生成式工场（Studio Panel）
POST /teacher/studio/generate      # 统一生成接口
GET  /teacher/studio/task/{task_id}  # 查询生成进度
GET  /teacher/studio/content/{content_id}  # 获取生成内容
PUT  /teacher/studio/content/{content_id}  # 更新生成内容
DELETE /teacher/studio/content/{content_id}  # 删除生成内容
POST /teacher/studio/content/{content_id}/export  # 导出内容

# 知识库高级管理（独立页面）
GET  /teacher/knowledge-base/graph       # 获取知识图谱
PUT  /teacher/knowledge-base/graph/{node_id}  # 编辑图谱节点
POST /teacher/knowledge-base/graph/export  # 导出图谱

# 学情分析（独立页面）
GET  /teacher/analytics/concept-mastery  # 概念掌握度
GET  /teacher/analytics/concept-correlations  # 关联分析
GET  /teacher/analytics/intervention-suggestions  # 干预建议
```

**新增服务模块**:
```
api/Edu_AI/app/teacher/
├── __init__.py
├── sources.py          # 知识库管理（文档上传、深度研究）
├── studio.py           # 生成式工场（统一生成接口）
├── knowledge_base.py   # 知识库高级管理（图谱编辑等）
└── analytics.py        # 学情分析
```

### 3.3 数据模型扩展

**知识图谱模型**:
```python
class KnowledgeNode(BaseModel):
    id: str
    name: str  # 概念名称
    type: str  # 类型：definition/example/application
    description: str
    metadata: Dict[str, Any]  # 章节、难度等

class KnowledgeEdge(BaseModel):
    id: str
    source_id: str  # 源节点ID
    target_id: str  # 目标节点ID
    relation_type: str  # 关系类型：depends_on/is_example_of
    strength: float  # 关联强度 0-1
```

**音频概览模型**:
```python
class AudioOverview(BaseModel):
    id: str
    title: str
    chapters: List[str]  # 关联的章节ID
    script: List[ScriptSegment]  # 对话脚本
    audio_url: str
    duration: float  # 秒
    timestamps: List[Timestamp]  # 时间戳索引
    created_at: datetime
```

## 四、实施计划

### 阶段一：统一模型交互界面基础功能（优先级：高）
1. **扩展SourcePanel**：
   - 文档上传进度显示
   - 文档预览功能
   - 深度研究入口集成
   
2. **扩展ChatPanel**：
   - 引用来源显示
   - 模型选择器
   - RAG开关
   - 对话历史管理
   
3. **扩展StudioPanel**：
   - 生成按钮扩展（报告、习题、博客、教案、音频、导图）
   - 生成配置面板
   - 生成内容预览和编辑

**预计时间**: 2-3周

### 阶段二：后端API开发（优先级：高）
1. **文档管理API**：
   - 文档上传和解析
   - 深度研究智能体（LangGraph工作流）
   
2. **生成式工场API**：
   - 统一生成接口
   - 各类型生成的实现（报告、习题、博客、教案、音频）
   - 异步任务管理
   
3. **对话管理API**：
   - 对话历史管理
   - 消息编辑和重新生成

**预计时间**: 3-4周

### 阶段三：知识库高级管理页面（优先级：中）
1. 知识图谱可视化编辑器
2. 图谱编辑功能
3. 文档高级管理功能

**预计时间**: 2周

### 阶段四：学情分析仪表盘（优先级：中）
1. 知识图谱热力图
2. 交互深度分析
3. 干预建议生成

**预计时间**: 2周

### 阶段五：优化与集成（优先级：中）
1. 性能优化
2. UI/UX优化
3. 与现有系统集成测试
4. 音频播放器组件开发

**预计时间**: 1-2周

## 五、关键技术依赖

### 5.1 新增依赖

**后端**:
```txt
# 文档解析
mineru  # PDF解析引擎（如果可用）
unstructured  # 备选方案

# 工作流编排
langgraph  # Agent工作流
langchain  # LLM集成

# 搜索与抓取
tavily-python  # 搜索API
firecrawl-py  # 网页抓取

# TTS
openai  # OpenAI TTS API
# 或
elevenlabs  # ElevenLabs API

# 图谱可视化（后端数据处理）
networkx  # 图谱算法
```

**前端**:
```json
{
  "@antv/g6": "^5.x",  // 或 react-force-graph
  "react-audio-player": "^x.x"  // 音频播放
}
```

### 5.2 现有依赖检查
- FastAPI ✓
- React + TypeScript ✓
- Ant Design ✓
- ChromaDB/Milvus（向量数据库）✓

## 六、风险评估与应对

### 6.1 技术风险
1. **Mineru集成复杂性**
   - 风险：Mineru可能依赖复杂环境
   - 应对：准备Unstructured作为备选方案

2. **TTS成本控制**
   - 风险：高质量TTS API成本较高
   - 应对：支持本地TTS模型（如coqui-tts）作为备选

3. **LangGraph学习曲线**
   - 风险：团队需要学习新框架
   - 应对：提供详细文档和示例代码

### 6.2 业务风险
1. **功能复杂度**
   - 风险：功能过多可能导致界面混乱
   - 应对：采用Tab/侧边栏导航，清晰的功能分组

2. **性能问题**
   - 风险：知识图谱可视化可能卡顿
   - 应对：使用虚拟化、分页加载

## 七、成功指标

1. **功能完整性**
   - [ ] 统一模型交互界面：三栏布局正常工作
   - [ ] 左侧栏：文档上传、深度研究、文档管理
   - [ ] 中间栏：对话交互、RAG检索、引用显示
   - [ ] 右侧栏：所有生成功能（报告、习题、博客、教案、音频、导图）
   - [ ] 知识库高级管理：知识图谱可视化编辑
   - [ ] 学情分析：可视化展示概念掌握度

2. **用户体验**
   - 教师能够在统一界面完成所有模型交互任务
   - 文档上传和解析流程顺畅，进度清晰
   - 音频生成成功率 > 90%
   - 生成内容预览和编辑体验良好
   - 学情分析数据更新延迟 < 5分钟

3. **技术指标**
   - API响应时间 < 2s（除异步任务）
   - 前端页面加载时间 < 3s
   - 知识图谱可视化支持 > 500个节点
   - 支持同时管理 > 100个文档

## 八、界面设计说明

### 8.1 统一模型交互界面布局

**布局结构**（基于现有的frontend/App.tsx）：
```
┌─────────────────────────────────────────────────────────┐
│ Header: NotebookLM-Lite                                  │
├──────────┬──────────────────────────────┬────────────────┤
│          │                              │                │
│ Source   │        Chat Panel            │   Studio      │
│ Panel    │        (中间栏)               │   Panel       │
│ (左侧栏) │                              │   (右侧栏)     │
│          │  - 消息列表                  │                │
│ - 文档   │  - 输入框                    │  - 生成按钮    │
│   列表   │  - 引用来源                  │  - 文件列表    │
│ - 上传   │                              │  - 内容预览    │
│ - 深度   │                              │                │
│   研究   │                              │                │
│          │                              │                │
└──────────┴──────────────────────────────┴────────────────┘
```

### 8.2 界面状态管理

使用Zustand进行状态管理（基于现有的useStore.ts扩展）：
```typescript
interface AppState {
  // 文档管理
  documents: Document[];
  selectedDocs: string[];
  
  // 对话管理
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  
  // 生成内容管理
  generatedContents: GeneratedContent[];
  viewingContent: GeneratedContent | null;
  
  // 上传/生成任务
  uploadTasks: UploadTask[];
  generateTasks: GenerateTask[];
}
```

### 8.3 响应式设计

- 左侧栏和右侧栏支持折叠（已有功能）
- 在移动端可以隐藏侧边栏，只显示中间对话栏
- 保持现有的折叠/展开交互逻辑


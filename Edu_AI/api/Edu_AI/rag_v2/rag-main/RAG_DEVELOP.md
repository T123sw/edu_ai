# RAG系统开发文档

## 项目RAG架构透明化分析

### 1. RAG系统整体架构

当前项目已经实现了一个完整的RAG（检索增强生成）系统，架构如下：

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端层 (React/TypeScript)                 │
├─────────────────────────────────────────────────────────────────┤
│  ChatPage.tsx     │  DocsPage.tsx     │  KnowledgeBasePage.tsx  │
│  (智能问答)        │  (文档管理)        │  (知识库浏览)              │
├─────────────────────────────────────────────────────────────────┤
│                    API服务层 (TypeScript)                        │
│  chat.ts          │  rag.ts           │  teacher.ts             │
├─────────────────────────────────────────────────────────────────┤
│                    后端API层 (FastAPI)                           │
│  main.py          │  rag_v2/api.py    │  core/config.py         │
├─────────────────────────────────────────────────────────────────┤
│                    RAG核心层 (Python)                            │
│  RAGSystem        │  EmbeddingClient  │  VectorStore            │
│  DocumentProcessor│                   │                         │
├─────────────────────────────────────────────────────────────────┤
│                    存储层                                        │
│  ChromaDB         │  document_index   │  conversations          │
│  (向量数据库)      │  (文档索引)        │  (对话历史)                │
└─────────────────────────────────────────────────────────────────┘
```

### 2. RAG系统核心组件分析

#### 2.1 RAGSystem (主控制器)
**位置**: `api/Edu_AI/rag_v2/rag_main/system.py`

**职责**:

- 统一管理整个RAG流程
- 协调文档处理、向量存储、检索和生成
- 提供增量导入和问答接口

**核心方法**:
```python
class RAGSystem:
    def __init__(self, api_base, api_key, embedding_model, llm_model, ...)
    def import_document(self, file_path, force_reimport=False, progress_callback=None)
    def query(self, question, top_k=5, conversation_history=None, llm_config=None)
    def list_documents(self)
    def delete_document(self, file_path)
    def get_document_details(self, file_path)
    def summarize_document(self, file_path, force_refresh=False)
```

#### 2.2 EmbeddingClient (向量化客户端)
**支持后端**: OpenAI兼容接口 / Ollama原生接口

**配置方式**:
```python
# OpenAI兼容模式 (默认)
EMBEDDING_BACKEND=openai
EMBEDDING_API_BASE=http://your-api/v1
EMBEDDING_MODEL=text-embedding-ada-002

# Ollama模式
EMBEDDING_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
```

**核心功能**:
- 批量文档向量化 (`embed_documents`)
- 查询向量化 (`embed_query`)
- 自动处理不同后端的API差异

#### 2.3 VectorStore (向量数据库)
**技术栈**: ChromaDB + 持久化存储

**核心功能**:
```python
class VectorStore:
    def add_documents(self, documents, embeddings, ids=None)
    def search(self, query_embedding, top_k=5)
    def delete_by_source(self, source)
    def get_documents_by_source(self, source)
    def get_document_count(self)
```

**存储结构**:
- 集合名称: "documents"
- 相似度算法: cosine
- 元数据字段: source, document_name, page等

#### 2.4 DocumentProcessor (文档处理器)
**支持格式**: 当前仅支持PDF

**处理流程**:
1. PDF加载 (PyMuPDFLoader)
2. 文本分块 (RecursiveCharacterTextSplitter)
3. 元数据提取

**分块配置**:
```python
chunk_size = 1000        # 分块大小
chunk_overlap = 200      # 重叠大小
separators = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]
```

### 3. RAG数据流程分析

#### 3.1 文档导入流程
```
用户上传PDF → 临时存储 → 文档解析 → 文本分块 → 向量化 → 存储到ChromaDB → 更新索引
     ↓              ↓           ↓          ↓         ↓            ↓
  前端进度条    upload_temp   PyMuPDF   TextSplitter  Embedding   VectorStore
   (0-50%)      (job_id)     (pages)    (chunks)     (vectors)   (persist)
```

**进度跟踪**:
- 上传阶段: 0-50% (真实上传进度)
- 处理阶段: 50-100% (解析→分块→向量化→存储)

**增量导入机制**:

- 基于文件MD5哈希检测变化
- 支持强制重新导入
- 自动清理旧数据

#### 3.2 RAG问答流程
```
用户问题 → 问题向量化 → 向量检索 → 文档过滤 → 上下文构建 → LLM生成 → 返回答案
    ↓           ↓           ↓          ↓           ↓           ↓         ↓
  question   embed_query   search   filter_docs  build_context call_llm  response
```

**检索策略**:
1. 向量相似度检索 (top_k * 3)
2. 文档参与度过滤 (include_in_search)
3. 最终选择 (top_k个文档)

**上下文构建**:
```python
messages = [
    {"role": "system", "content": "你是qwen3-8b，一个乐于助人的助手。"},
    # 历史对话 (最近N轮)
    *conversation_history[-CHAT_HISTORY_WINDOW:],
    # 当前问题 + 检索上下文
    {"role": "user", "content": f"【参考资料】\n{kb_context}\n\n问题：{question}"}
]
```

### 4. 存储架构分析

#### 4.1 向量数据库 (ChromaDB)
**存储路径**: `storage/vector_db/`
**数据结构**:
```
Collection: documents
├── embeddings: List[List[float]]  # 向量数据
├── documents: List[str]           # 文档内容
├── metadatas: List[Dict]          # 元数据
└── ids: List[str]                 # 文档ID
```

#### 4.2 文档索引 (JSON)
**存储路径**: `storage/document_index.json`
**数据结构**:
```json
{
  "/path/to/document.pdf": {
    "hash": "md5_hash",
    "imported_at": "2025-01-01T00:00:00",
    "chunk_count": 50,
    "file_name": "document.pdf",
    "file_size": 1024000,
    "page_count": 10,
    "include_in_search": true,
    "summary": "文档摘要",
    "summary_updated_at": "2025-01-01T00:00:00"
  }
}
```

#### 4.3 对话历史 (JSON)
**存储路径**: `storage/conversations.json`
**用途**: 支持多轮对话上下文

### 5. API接口分析

#### 5.1 RAG专用接口 (`/api/rag/*`)
```python
# 文档管理
POST   /api/rag/upload_temp          # 上传临时文件
POST   /api/rag/import/path          # 从路径导入
GET    /api/rag/import/progress      # 查询导入进度
GET    /api/rag/documents            # 列出文档
DELETE /api/rag/document/{path}      # 删除文档
PATCH  /api/rag/document/participation # 设置检索参与度

# 文档详情
GET    /api/rag/document/details     # 获取文档详情
POST   /api/rag/document/summary     # 生成/获取摘要

# 问答和统计
POST   /api/rag/query               # RAG问答
GET    /api/rag/stats               # 获取统计信息
```

#### 5.2 聊天接口 (`/chat`)
**集成方式**: 直接调用RAGSystem.query()
**特点**: 
- 支持对话历史上下文
- 自动生成对话标题
- 持久化对话记录

### 6. 前端集成分析

#### 6.1 服务层封装
**文件**: `src/services/rag.ts`
**主要功能**:
```typescript
// 核心功能
ragQuery(question, top_k)           // RAG问答
importDocument(file, forceReimport, onProgress)  // 文档导入
listDocuments()                     // 文档列表
getDocumentDetails(filePath)        // 文档详情
updateDocumentParticipation(...)    // 设置检索参与度

// 进度管理
uploadTempWithProgress(...)         // 上传进度
getImportProgress(jobId)           // 导入进度
```

#### 6.2 页面集成
- **ChatPage**: 使用chat.ts调用/chat接口 (内部使用RAG)
- **DocsPage**: 使用rag.ts管理文档上传和列表
- **KnowledgeBasePage**: 目前使用模拟数据，待接入真实RAG数据

### 7. 当前RAG系统的优势

#### 7.1 已实现的核心功能
✅ **完整的RAG流程**: 文档导入→向量化→检索→生成
✅ **增量导入**: 基于文件哈希的智能更新
✅ **进度跟踪**: 实时上传和处理进度
✅ **多模型支持**: OpenAI/Ollama兼容
✅ **对话上下文**: 支持多轮对话历史
✅ **文档管理**: 完整的CRUD操作
✅ **检索控制**: 可控制文档是否参与检索
✅ **自动摘要**: LLM生成文档摘要

#### 7.2 架构优势
✅ **模块化设计**: 各组件职责清晰，易于扩展
✅ **配置灵活**: 支持多种embedding后端
✅ **错误处理**: 完善的异常处理机制
✅ **持久化**: 数据持久化存储
✅ **API标准化**: RESTful API设计

### 8. 扩展机会和改进方向

#### 8.1 多模态RAG扩展点

**当前限制**: 仅支持PDF文本内容
**扩展机会**:
1. **图像内容提取**: PDF中的图表、图片
2. **多模态向量化**: 文本+图像联合embedding
3. **视觉问答**: 基于图像内容的问答

**具体扩展接口**:
```python
# 在DocumentProcessor中扩展
class DocumentProcessor:
    def extract_images(self, file_path: str) -> List[Image]
    def extract_tables(self, file_path: str) -> List[Table]
    def process_multimodal_content(self, file_path: str) -> List[MultimodalDocument]

# 在EmbeddingClient中扩展
class EmbeddingClient:
    def embed_multimodal(self, texts: List[str], images: List[Image]) -> List[List[float]]
```

#### 8.2 图谱RAG扩展点

**当前限制**: 基于向量相似度的简单检索
**扩展机会**:
1. **知识图谱构建**: 从文档中提取实体和关系
2. **图谱增强检索**: 结合向量检索和图谱推理
3. **结构化知识**: 支持结构化知识表示

**具体扩展接口**:
```python
# 新增图谱组件
class KnowledgeGraph:
    def extract_entities(self, documents: List[Document]) -> List[Entity]
    def extract_relations(self, documents: List[Document]) -> List[Relation]
    def build_graph(self, entities: List[Entity], relations: List[Relation])
    def graph_search(self, query: str, top_k: int) -> List[GraphResult]

# 在RAGSystem中集成
class RAGSystem:
    def __init__(self, ..., enable_knowledge_graph=False):
        if enable_knowledge_graph:
            self.knowledge_graph = KnowledgeGraph()
    
    def hybrid_search(self, query: str, top_k: int) -> List[Document]:
        # 结合向量检索和图谱检索
        vector_results = self.vector_store.search(...)
        graph_results = self.knowledge_graph.graph_search(...)
        return self.merge_results(vector_results, graph_results)
```

### 9. 你的开发任务和接口

#### 9.1 现有可扩展接口

**DocumentProcessor扩展**:
```python
# 当前只支持PDF，你可以扩展
def load_images(self, file_path: str) -> List[Document]
def load_videos(self, file_path: str) -> List[Document]  
def load_audio(self, file_path: str) -> List[Document]
```

**EmbeddingClient扩展**:
```python
# 当前只支持文本embedding，你可以扩展
def embed_images(self, images: List[Image]) -> List[List[float]]
def embed_multimodal(self, content: MultimodalContent) -> List[float]
```

**VectorStore扩展**:
```python
# 当前使用ChromaDB，你可以替换或扩展
def add_multimodal_documents(self, documents, text_embeddings, image_embeddings)
def hybrid_search(self, text_query, image_query, top_k)
```

#### 9.2 配置扩展点

**环境变量扩展**:
```bash
# 多模态配置
MULTIMODAL_ENABLED=true
IMAGE_EMBEDDING_MODEL=clip-vit-base-patch32
VISION_API_BASE=http://localhost:8001

# 图谱配置  
KNOWLEDGE_GRAPH_ENABLED=true
GRAPH_DB_URL=neo4j://localhost:7687
ENTITY_EXTRACTION_MODEL=spacy_lg
```

#### 9.3 API扩展点

**新增接口建议**:
```python
# 多模态相关
POST /api/rag/import/multimodal     # 多模态文档导入
POST /api/rag/query/multimodal      # 多模态问答
GET  /api/rag/document/images       # 获取文档图像

# 图谱相关
POST /api/rag/graph/build           # 构建知识图谱
GET  /api/rag/graph/entities        # 获取实体列表
GET  /api/rag/graph/relations       # 获取关系列表
POST /api/rag/query/hybrid          # 混合检索问答
```

### 10. 开发建议

#### 10.1 开发优先级
1. **先熟悉现有架构**: 运行现有系统，理解数据流
2. **小步迭代**: 先扩展单一功能，如图像提取
3. **保持兼容**: 确保扩展不破坏现有功能
4. **完善测试**: 为新功能添加测试用例

#### 10.2 技术选型建议
**多模态RAG**:
- 图像embedding: CLIP, BLIP-2
- 多模态LLM: LLaVA, GPT-4V
- 图像处理: PIL, OpenCV

**图谱RAG**:
- 图数据库: Neo4j, ArangoDB
- 实体识别: spaCy, BERT-NER
- 关系抽取: OpenIE, 自定义模型

#### 10.3 数据来源分析

**当前知识库来源**:
1. **PDF文档**: 用户上传的教学材料
2. **数据采集**: 预留的爬虫接口 (DataPipelinePage)

**图像内容来源**:
- PDF中的图表、示意图
- 教学课件中的图片
- 实验图片、设备图片

**潜在扩展**:
- 视频课程内容
- 音频讲座内容
- 在线教学资源

### 11. 总结

当前RAG系统已经是一个**功能完整、架构清晰**的实现，为你的图谱RAG和多模态RAG扩展提供了**坚实的基础**。

**你的主要任务**:
1. 在现有DocumentProcessor基础上扩展多模态内容提取
2. 在现有EmbeddingClient基础上支持多模态向量化  
3. 在现有VectorStore基础上支持混合检索
4. 在现有RAGSystem基础上集成图谱推理

**关键优势**:
- 现有架构模块化程度高，易于扩展
- API接口设计规范，便于集成
- 前端已有完整的服务层封装
- 配置系统灵活，支持多种部署方式

你可以专注于**核心算法和模型集成**，而不需要从零构建基础设施。

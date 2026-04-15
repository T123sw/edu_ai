# rag_v2 后端兼容接入设计

**日期**: 2026-04-15  
**状态**: 待评审  
**范围**: Edu_AI 后端将当前 `new_rag` 运行链路切换为基于 `rag_v2` 的兼容接入层，第一阶段只做兼容替换，不开启新 RAG 扩展能力。

## 1. 背景

当前后端运行时仍然统一依赖 `new_rag`：

- 主入口 [app/main.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/main.py:22) 挂载了 `new_rag.api` 的 `rag_router`，并在多个业务接口里直接调用 `get_rag_system()`
- 课程知识库、DeepSearch、Blog Agent、聊天工具和知识库 provider 也都直接导入 `new_rag.api`
- 业务层不仅依赖公开路由和公开方法，还直接依赖 `RAGSystem` 的内部属性和内部辅助方法

用户已经把新的 RAG 源码放到了 `rag_v2/rag-main/` 下，希望后续逐步替换掉当前 `new_rag`。本设计文档的目标，是在不一次性改动所有业务语义的前提下，先完成一版低风险的后端兼容接入。

## 2. 现状分析

### 2.1 当前运行中的接入点

当前后端直接依赖 `new_rag.api` 的主要位置包括：

- [app/main.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/main.py:22)
- [app/courses.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/courses.py:15)
- [app/deepsearch.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py:20)
- [app/deepsearch_pipeline.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py:12)
- [app/blog_agent/engine.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/blog_agent/engine.py:10)
- [app/chat/application/knowledge_base_summary_provider.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py:6)
- [app/chat/application/knowledge_base_document_content_provider.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py:6)
- [app/chat/tools/agent_tools.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py:10)
- [app/chat/tools/search_tools.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py:11)

这意味着所谓“开始对接”并不是单点切换，而是一条横跨主路由、课程、深度搜索、聊天和内容生成的共享基础设施切换。

### 2.2 业务层对 RAGSystem 的真实依赖

当前业务层不仅使用公开方法，还直接读取或调用了下面这些内部能力：

- `rag_system.document_index`
- `rag_system.document_processor.load_pdf/load_doc/load_text_like`
- `rag_system.vector_store.get_documents_by_source(...)`
- `rag_system._make_index_key(...)`
- `rag_system._make_source_key(...)`
- `rag_system._save_index()`
- `rag_system._call_llm(...)`

其中典型调用点包括：

- [app/deepsearch.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py:380)
- [app/deepsearch_pipeline.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py:159)
- [app/main.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/main.py:342)
- [app/chat/application/knowledge_base_document_content_provider.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py:47)

这说明第一阶段不能只做“路由切换”或“HTTP 层切换”，还必须确保 `get_rag_system()` 返回的对象在对象结构上与当前运行期足够兼容。

### 2.3 新旧 RAG 核心方法对比

`new_rag/system.py` 和 `rag_v2/rag-main/system.py` 都具备以下核心方法：

- `import_document(...)`
- `query(...)`
- `list_documents(...)`
- `update_document_participation(...)`
- `get_document_details(...)`
- `summarize_document(...)`
- `get_stats(...)`
- `delete_document(...)`

同时，新旧两边也都包含：

- `VectorStore`
- `DocumentProcessor`
- `document_index`
- 以 owner 隔离的索引 key/source key 能力

这意味着从“对象能力集合”角度看，`rag_v2/rag-main/system.py` 是可以作为第一阶段底层 `RAGSystem` 候选实现的。

### 2.4 新旧 API 路由面差异

`new_rag/api.py` 已经对外提供了当前后端真正使用的路由集合，例如：

- `/api/rag/query`
- `/api/rag/import`
- `/api/rag/import/path`
- `/api/rag/stats`
- `/api/rag/documents`
- `/api/rag/document/rename`
- `/api/rag/document/participation`
- `/api/rag/document/details`
- `/api/rag/document/summary`
- `/api/rag/document/content`

`rag_v2/rag-main/api.py` 在保留这些核心路由的同时，又新增了：

- `/api/rag/query_stream`
- `/api/rag/import_image`
- `/api/rag/import_video`

以及更丰富的 QueryRequest 字段，例如：

- `use_enhanced_retrieval`
- `hyde_weight`
- `use_rrf`
- `conversation_history`

这说明 `rag_v2/rag-main/api.py` 不是单纯的“更高版本同接口实现”，而是“同一基础接口上继续扩展的新入口”。第一阶段如果直接整体暴露它，等于把还没被业务验证的新能力也一起推到主后端入口，风险偏高。

### 2.5 最大技术风险：`rag-main` 当前不是可安全直接导入的宿主包

`rag_v2/rag-main/api.py` 当前采用的是独立项目风格导入：

- `from system import RAGSystem`
- `from core.config import Config`
- `from app.auth import get_current_user`

这里最危险的是 `from core.config import Config`。

主后端项目自己已经存在 [core/config.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/core/config.py:1)，而 `rag-main` 内部也有一份不同语义的 [rag_v2/rag-main/core/config.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag-main/core/config.py:1)。这两份 `Config` 的路径语义和默认存储路径不同：

- 主项目 `core.config.Config` 以整站 `storage/` 为基础
- `rag-main/core/config.py` 以 `rag-main` 自身目录为基础，且默认写入 `knowledge_base/`、`storage/`、`temp/`

因此，第一阶段不能用“把 `rag-main` 路径塞进 `sys.path` 然后直接 import 它的 api.py”这种做法。这样会带来三个问题：

1. `core.config` 解析来源不稳定，可能错误落到主项目 `core.config`
2. `system`、`api` 这类顶级模块名过于泛化，容易和宿主项目模块冲突
3. 直接整体暴露 `rag-main/api.py` 会把尚未纳管的新扩展路由一起挂载出来

## 3. 设计目标

第一阶段目标：

- 让后端主入口和所有主要业务调用点从 `new_rag.api` 切到 `rag_v2.api`
- 保持当前业务调用方式基本不变
- 保持 `/api/rag` 兼容路由面不变
- `get_rag_system()` 返回可兼容当前业务层内部依赖的真实对象
- 保留 `new_rag` 目录和实现作为回退参考

第一阶段非目标：

- 不重写课程、DeepSearch、聊天工具的业务逻辑
- 不一次性接入图片入库、视频入库、流式问答、增强检索开关等新能力到生产主链路
- 不删除 `new_rag`
- 不在这一轮里处理所有测试改造

## 4. 方案对比

### 方案 A：直接把 `app/main.py` 改成挂载 `rag_v2/rag-main/api.py`

做法：

- 直接加载 `rag-main/api.py`
- 业务层保持现状

优点：

- 表面改动最少

缺点：

- `core.config` 冲突高风险
- `system`/`api` 顶级导入不安全
- 新扩展路由会一并暴露
- 依赖 `sys.path` 和模块别名技巧，长期难维护

结论：

- 不推荐

### 方案 B：保留 `new_rag` 名称，内部偷偷改成代理 `rag_v2`

做法：

- `new_rag/api.py` 改造成转发层
- 业务调用点不改

优点：

- 短期改动面最小

缺点：

- 名称与实现不一致，后续排障最痛苦
- `new_rag` 失去“回退参考”价值
- 未来彻底迁移时还得再做一轮换名

结论：

- 可作为临时应急回退方案，不作为主方案

### 方案 C：构建 `rag_v2` 兼容接入层，统一切换业务导入

做法：

- 在 `rag_v2` 下建立一个可安全导入的运行时包
- 在 `rag_v2/api.py` 中只暴露和 `new_rag/api.py` 对齐的兼容路由
- 在 `rag_v2/system.py` 中对外暴露兼容的 `RAGSystem`
- 把所有业务导入从 `new_rag.api` 切到 `rag_v2.api`

优点：

- 路径清晰
- 风险可控
- 后续逐步启用新能力时有明确落点
- `new_rag` 仍可保留作为回退

缺点：

- 需要一层明确的兼容包装
- 需要先解决 `rag-main` 的包结构导入问题

结论：

- 推荐方案

## 5. 推荐方案

### 5.1 总体思路

第一阶段不直接对外暴露 `rag_v2/rag-main/api.py`，而是：

1. 先把 `rag-main` 的运行时代码整理成宿主项目内可安全导入的包结构
2. 再由 `rag_v2/api.py` 提供一套和 `new_rag/api.py` 对齐的兼容路由
3. 业务层统一改为依赖 `rag_v2.api`
4. 底层真正执行的 `RAGSystem` 切换为新实现

### 5.2 包结构建议

推荐新增一个真正用于运行的 Python 包目录：

- `Edu_AI/api/Edu_AI/rag_v2/rag_main/`

用途：

- 作为宿主后端真正 import 的运行时代码目录
- 将 `rag_v2/rag-main/` 视为“外部导入快照/原始源码落地区”，不直接挂到主应用运行链路上

原因：

- `rag-main` 目录名包含 `-`，不适合作为 Python 包名
- 当前里面使用了独立项目式绝对导入，直接加载容易与宿主项目冲突
- 通过 `rag_main` 这种规范包名承接运行时，更利于后续维护和升级

### 5.3 运行时代码整理原则

`rag_v2/rag_main/` 中的代码应当来自当前 `rag_v2/rag-main/`，但需要做最小必要的包规范化处理：

- 把 `from system import RAGSystem` 改为相对导入
- 把 `from core.config import Config` 改为包内相对导入
- 保持对宿主项目认证、宿主项目业务模型的引用仍然走宿主项目路径，例如 `app.auth`

换句话说，第一阶段不是重写新 RAG，而是把它从“独立运行项目”整理为“可被宿主后端稳定引用的内部包”。

### 5.4 `rag_v2` 对外暴露层

第一阶段 `rag_v2` 只对外暴露兼容层：

- `rag_v2/api.py`
- `rag_v2/system.py`
- `rag_v2/__init__.py`

职责如下。

#### `rag_v2/system.py`

职责：

- 对外导出新运行时里的 `RAGSystem`
- 保持业务层通过 `get_rag_system()` 获得的对象能力集合不变

要求：

- 返回对象必须保留当前业务依赖的内部能力
- 至少兼容：
  - `document_index`
  - `document_processor`
  - `vector_store`
  - `_make_index_key`
  - `_make_source_key`
  - `_save_index`
  - `_call_llm`

#### `rag_v2/api.py`

职责：

- 提供兼容版 `/api/rag` 路由
- 提供 `get_rag_system()`
- 封装单例初始化逻辑
- 暂时只暴露与 `new_rag/api.py` 对齐的接口面

第一阶段兼容路由范围：

- `upload_temp`
- `query`
- `import`
- `import/path`
- `stats`
- `documents`
- `document/rename`
- `document/participation`
- `document/details`
- `document/summary`
- `document/content`
- `image`
- `delete_document`

第一阶段不对主后端统一暴露的新扩展路由：

- `query_stream`
- `import_image`
- `import_video`

这样做的目的，是先确保现有主业务流切换成功，再决定哪些新能力要以什么形式进入正式接口。

#### `rag_v2/__init__.py`

职责：

- 提供统一导出
- 至少暴露：
  - `RAGSystem`
  - `rag_router`
  - `get_rag_system`

### 5.5 业务导入切换

切换后的导入目标应统一为：

- `from rag_v2.api import router as rag_router, get_rag_system`

或：

- `from rag_v2.api import get_rag_system`

需要切换的首批文件包括：

- [app/main.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/main.py:22)
- [app/courses.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/courses.py:15)
- [app/deepsearch.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py:20)
- [app/deepsearch_pipeline.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py:12)
- [app/blog_agent/engine.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/blog_agent/engine.py:10)
- [app/chat/application/knowledge_base_summary_provider.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py:6)
- [app/chat/application/knowledge_base_document_content_provider.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py:6)
- [app/chat/tools/agent_tools.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py:10)
- [app/chat/tools/search_tools.py](/d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py:11)

### 5.6 `new_rag` 的处理方式

第一阶段：

- 不删除 `new_rag`
- 不在主链路继续引用 `new_rag`
- 保留其代码作为回退和对照实现

这是因为当前项目里仍有很多地方默认把 `new_rag` 视为“生产基线”，在 `rag_v2` 首轮切换完成前，保留参考系更安全。

## 6. 文件改动范围

第一阶段预计涉及以下核心文件。

### 新增

- `Edu_AI/api/Edu_AI/rag_v2/api.py`
- `Edu_AI/api/Edu_AI/rag_v2/system.py`
- `Edu_AI/api/Edu_AI/rag_v2/rag_main/__init__.py`
- `Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py`
- `Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py`
- `Edu_AI/api/Edu_AI/rag_v2/rag_main/core/config.py`

说明：

- 这里的 `rag_main/` 是运行时包
- 其内容来源于 `rag_v2/rag-main/`，但做最小必要规范化

### 修改

- `Edu_AI/api/Edu_AI/rag_v2/__init__.py`
- `Edu_AI/api/Edu_AI/app/main.py`
- `Edu_AI/api/Edu_AI/app/courses.py`
- `Edu_AI/api/Edu_AI/app/deepsearch.py`
- `Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py`
- `Edu_AI/api/Edu_AI/app/blog_agent/engine.py`
- `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py`
- `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py`
- `Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py`
- `Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py`

### 暂不改

- `Edu_AI/api/Edu_AI/new_rag/**`
- 与第一阶段兼容接入无关的业务逻辑文件
- 测试文件

## 7. 风险与缓解

### 风险 1：业务层依赖私有属性，兼容层只做公开 API 会不够

表现：

- 切了 `get_rag_system()` 以后，运行期仍然在 `document_index`、`document_processor`、`vector_store` 等处报错

缓解：

- 第一阶段必须返回真实 `RAGSystem` 对象，而不是只返回 HTTP 客户端或弱包装对象
- 实现前先以“业务实际依赖清单”为准做兼容校对

### 风险 2：`core.config` 冲突导致新 RAG 写错目录

表现：

- 向量库、索引文件、临时文件落到不符合预期的位置
- 出现“导入成功但查询不到”“新旧索引各写一份”的情况

缓解：

- 不采用直接 `sys.path` 注入 + 顶级模块导入的做法
- 把运行时代码整理为包内相对导入
- 在 `rag_v2/rag_main/core/config.py` 中显式定义第一阶段使用的路径语义

### 风险 3：同一进程里同时存在两套 RAG 单例

表现：

- 一部分代码还在 import `new_rag.api`
- 另一部分代码已经切到 `rag_v2.api`
- 导入、查询、删除操作落在不同单例上

缓解：

- 业务导入切换要一次性完成到 `rag_v2.api`
- 切换完成前，不做“部分文件先切、部分文件后切”的长期中间态

### 风险 4：误把未验证新能力暴露到正式接口

表现：

- `/query_stream`
- `/import_image`
- `/import_video`

被主应用一起挂载，但前端和权限控制尚未统一设计

缓解：

- 第一阶段 `rag_v2/api.py` 使用兼容路由面，不直接暴露全部 `rag-main/api.py`

### 风险 5：新 RAG 的环境依赖比旧版更重

表现：

- MinerU
- ffmpeg / ffprobe
- 多模态 embedding
- 额外索引文件

在部署环境上引入新的运行前置条件

缓解：

- 第一阶段仅切兼容主链路
- 对图片/视频路由保持未对主入口开放状态
- 在主链路中只依赖当前已验证可运行的文档导入与文本问答能力

## 8. 回退策略

如果第一阶段切换后出现严重问题，回退方式应当简单直接：

1. 把所有 `from rag_v2.api ...` 导入恢复为 `from new_rag.api ...`
2. 主入口恢复挂载 `new_rag.api` 的 `rag_router`
3. 保留 `rag_v2` 代码，不做删除

因为 `new_rag` 第一阶段不删除，所以回退成本应控制在“导入源回切”级别。

## 9. 阶段划分

### 阶段 1：兼容接入

目标：

- 让主后端运行在 `rag_v2` 之上
- 业务接口不改语义
- 主入口只保留兼容接口面

交付：

- `rag_v2/api.py`
- `rag_v2/system.py`
- 包规范化后的 `rag_v2/rag_main/`
- 业务导入统一切换

### 阶段 2：启用新能力

候选内容：

- 增强检索参数对外开放
- 流式问答
- 图片入库
- 视频入库
- 新索引能力与新响应字段

前提：

- 阶段 1 兼容接入稳定
- 新能力有明确的业务入口和权限边界

### 阶段 3：收尾清理

候选内容：

- 评估是否删除 `new_rag`
- 评估是否将 `rag_v2/rag-main/` 作为只读快照保留
- 统一文档与结构说明

## 10. 第一阶段验收标准

满足以下条件可视为第一阶段完成：

1. 主应用 `app/main.py` 已挂载 `rag_v2.api` 的 `rag_router`
2. 所有当前生产调用点都已从 `new_rag.api` 切换到 `rag_v2.api`
3. `get_rag_system()` 返回对象可被当前业务层现有调用直接使用
4. 现有 `/api/rag` 兼容路由面保持可用
5. 第一阶段未把 `/query_stream`、`/import_image`、`/import_video` 暴露到主兼容入口
6. `new_rag` 仍保留在仓库中作为回退参考

## 11. 明确结论

本次对接不应采用“直接 import `rag_v2/rag-main/api.py` 并挂载”的方式。  
推荐做法是：

- 先把 `rag-main` 的运行时代码规范化为可安全导入的宿主包
- 再由 `rag_v2/api.py` 提供与 `new_rag/api.py` 对齐的兼容入口
- 最后一次性切换全部业务导入源到 `rag_v2.api`

这样可以同时满足三件事：

- 底层切到新 RAG
- 现有业务逻辑尽量不动
- 新扩展能力先收住，不提前进入主链路

## 12. 后续动作建议

该 spec 通过后，下一步应进入实现计划阶段，输出一份明确的 implementation plan，重点覆盖：

- `rag_v2` 运行时包结构整理
- 兼容 API 文件拆分
- 导入源切换顺序
- 验证与回退步骤


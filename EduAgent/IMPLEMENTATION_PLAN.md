# 深度搜索 + 爬虫 + 前端渲染功能实现计划

## 📋 功能概述

实现一个完整的流程：
1. **深度搜索** → 获取相关URL链接
2. **自动化爬虫** → 爬取URL内容（PDF/网页）
3. **内容清洗** → 处理并格式化内容
4. **前端渲染** → 展示清洗后的内容

## 🎯 实现步骤

### 阶段一：后端API集成（核心功能）

#### 步骤1.1：创建爬虫服务模块
**文件**: `EduAgent/services/crawler_service.py`

**功能**:
- 封装自动化爬虫模块的调用
- 支持批量爬取URL列表
- 返回爬取结果（成功/失败状态、文件路径、内容摘要）

**接口设计**:
```python
class CrawlerService:
    def crawl_urls(self, urls: List[str], output_path: str) -> Dict:
        """
        爬取URL列表
        返回: {
            "success": [...],  # 成功列表
            "failed": [...],   # 失败列表
            "results": [...]   # 详细结果
        }
        """
```

#### 步骤1.2：创建内容清洗模块
**文件**: `EduAgent/services/content_cleaner.py`

**功能**:
- 清洗HTML/文本内容
- 提取关键信息（标题、正文、元数据）
- 格式化内容（Markdown/纯文本）
- 处理PDF内容（提取文本）

**清洗规则**:
- 移除广告、导航栏、页脚
- 保留正文内容
- 提取标题和元数据
- 格式化文本（段落、列表等）

#### 步骤1.3：创建数据存储模块
**文件**: `EduAgent/services/storage_service.py`

**功能**:
- 存储爬取结果到数据库/文件系统
- 管理爬取历史
- 提供查询接口

**存储结构**:
```
crawled_data/
├── {query_id}/
│   ├── metadata.json      # 元数据
│   ├── {url_hash}_content.txt  # 清洗后的内容
│   └── {url_hash}_raw.html     # 原始HTML（可选）
```

#### 步骤1.4：创建集成API端点
**文件**: `EduAgent/main.py` (新增端点)

**API设计**:
```python
POST /agent/deepsearch-and-crawl
{
    "query": "计算思维 课程大纲 PDF",
    "max_urls": 10,  # 最多爬取的URL数量
    "crawl_timeout": 30  # 单个URL爬取超时（秒）
}

返回:
{
    "ok": true,
    "query": "...",
    "search_results": [...],  # 搜索到的URL
    "crawl_results": {
        "success_count": 5,
        "failed_count": 3,
        "results": [
            {
                "url": "...",
                "title": "...",
                "content": "...",  # 清洗后的内容
                "content_type": "text|pdf",
                "file_path": "...",
                "status": "success|failed"
            }
        ]
    }
}
```

### 阶段二：内容清洗优化

#### 步骤2.1：增强文本提取
- 使用 trafilatura（已有）提取正文
- 添加 Readability 算法备用
- 处理特殊格式（表格、代码块）

#### 步骤2.2：PDF内容提取
- 集成主线 MinerU 导入管线处理 PDF 文本
- 处理PDF中的图片和表格
- 提取PDF元数据（标题、作者等）

#### 步骤2.3：内容格式化
- 转换为Markdown格式
- 保留标题层级
- 处理链接和图片
- 清理多余空白

### 阶段三：前端API设计

#### 步骤3.1：获取爬取结果列表
```python
GET /agent/crawl-results/{query_id}
返回: 爬取结果列表
```

#### 步骤3.2：获取单个内容详情
```python
GET /agent/crawl-content/{content_id}
返回: {
    "url": "...",
    "title": "...",
    "content": "...",  # 清洗后的内容
    "metadata": {...}
}
```

#### 步骤3.3：搜索爬取历史
```python
GET /agent/crawl-history?query=...
返回: 历史爬取记录
```

### 阶段四：前端渲染

#### 步骤4.1：创建内容展示组件
**组件**: `ContentViewer.vue` 或 `ContentViewer.tsx`

**功能**:
- 展示清洗后的内容
- 支持Markdown渲染
- 显示元数据（URL、标题、爬取时间）
- 支持PDF预览

#### 步骤4.2：创建结果列表组件
**组件**: `CrawlResultsList.vue`

**功能**:
- 显示爬取结果列表
- 状态标识（成功/失败）
- 内容预览
- 点击查看详情

#### 步骤4.3：集成到主界面
- 在搜索页面添加"深度搜索并爬取"按钮
- 显示爬取进度
- 展示结果列表

## 📁 文件结构

```
EduAgent/
├── services/                    # 新增服务模块
│   ├── __init__.py
│   ├── crawler_service.py       # 爬虫服务
│   ├── content_cleaner.py       # 内容清洗
│   └── storage_service.py       # 存储服务
├── models/                      # 数据模型
│   ├── __init__.py
│   └── crawl_result.py          # 爬取结果模型
├── utils/                       # 工具函数
│   ├── __init__.py
│   └── text_processing.py      # 文本处理工具
├── main.py                      # 主API（新增端点）
└── IMPLEMENTATION_PLAN.md       # 本文档
```

## 🔧 技术栈

### 后端
- **FastAPI**: Web框架
- **自动化爬虫模块**: 已有模块
- **trafilatura**: 文本提取（已有）
- **MinerU**: PDF处理（主线导入管线）
- **BeautifulSoup**: HTML解析（已有）

### 前端
- **React/Vue**: 前端框架
- **Markdown渲染**: react-markdown / marked
- **PDF预览**: react-pdf / pdf.js

## 📝 详细实现步骤

### 第一步：创建服务模块基础结构

1. 创建 `services/` 目录
2. 创建 `crawler_service.py`，封装爬虫调用
3. 创建 `content_cleaner.py`，实现内容清洗
4. 创建 `storage_service.py`，实现存储管理

### 第二步：实现爬虫服务

1. 集成 `自动化爬虫/src/selenium_way/crawle_url.py`
2. 实现批量爬取逻辑
3. 添加错误处理和重试机制
4. 返回结构化结果

### 第三步：实现内容清洗

1. 文本内容清洗（HTML → Markdown）
2. PDF内容提取
3. 元数据提取
4. 内容格式化

### 第四步：创建API端点

1. 在 `main.py` 中添加 `/agent/deepsearch-and-crawl` 端点
2. 集成深度搜索 + 爬虫流程
3. 返回统一格式的响应

### 第五步：前端集成

1. 创建API调用函数
2. 创建内容展示组件
3. 创建结果列表组件
4. 集成到主界面

## ⚠️ 注意事项

1. **性能优化**
   - 异步爬取（使用 asyncio）
   - 限制并发数
   - 添加超时控制

2. **错误处理**
   - 网络错误重试
   - 无效URL跳过
   - 记录失败原因

3. **资源管理**
   - 及时关闭浏览器驱动
   - 清理临时文件
   - 限制存储空间

4. **安全性**
   - URL验证
   - 内容过滤（防止恶意内容）
   - 文件大小限制

## 🚀 快速开始

### 开发顺序

1. **先实现后端核心功能**（步骤1.1-1.4）
2. **测试爬虫集成**（确保能正常爬取）
3. **实现内容清洗**（步骤2.1-2.3）
4. **创建API端点**（步骤1.4）
5. **前端集成**（步骤4.1-4.3）

### 测试计划

1. 单元测试：各服务模块
2. 集成测试：深度搜索 → 爬虫 → 清洗流程
3. 端到端测试：完整流程（API → 前端）

## 📊 预期效果

- 用户输入查询 → 深度搜索获取URL
- 自动爬取URL内容 → 清洗格式化
- 前端展示清洗后的内容 → 用户查看

---

**下一步**: 开始实现步骤1.1 - 创建爬虫服务模块


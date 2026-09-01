# 课程文件存储管理系统

## 概述

课程存储管理系统用于统一管理所有课程相关的文件和数据，包括课程基础信息、知识库文件和教师生成的教学资料。

## 目录结构

```
course_data/
├── courses/                          # 所有课程数据
│   └── {course_id}/                  # 单个课程目录
│       ├── course_info.json          # 课程基础信息
│       ├── metadata.json             # 课程元数据（创建时间、更新时间等）
│       ├── knowledge_base/           # 课程知识库 (L1)
│       │   ├── documents/            # 文档文件
│       │   │   ├── doc1.pdf
│       │   │   ├── doc2.docx
│       │   │   └── ...
│       │   └── index.json            # 知识库索引文件
│       └── generated_materials/      # 教师生成的教学资料
│           ├── audio/                # 音频概览
│           │   ├── {material_id}.json
│           │   └── {material_id}.mp3 (可选附件)
│           ├── lesson_plans/         # 教案生成
│           │   ├── {material_id}.json
│           │   └── {material_id}.docx (可选附件)
│           ├── graphs/               # 思维导图
│           │   ├── {material_id}.json
│           │   └── {material_id}.png (可选附件)
│           ├── reports/              # 报告
│           │   ├── {material_id}.json
│           │   └── {material_id}.pdf (可选附件)
│           ├── blogs/                # 教学博客
│           │   ├── {material_id}.json
│           │   └── {material_id}.md (可选附件)
│           └── quizzes/              # 测验
│               ├── {material_id}.json
│               └── {material_id}.json (题目数据)
```

## 使用示例

### 1. 初始化存储管理器

```python
from Edu_AI.core.course_storage import storage_manager

# 使用默认配置（推荐）
manager = storage_manager

# 或使用自定义路径
from Edu_AI.core.course_storage import CourseStorageManager
manager = CourseStorageManager(root_path="/custom/path")
```

### 2. 创建课程目录结构

```python
course_id = "computational-thinking"
course_dir = manager.create_course_structure(course_id)
```

### 3. 保存课程基础信息

```python
course_info = {
    "id": "computational-thinking",
    "title": "计算思维",
    "description": "培养计算思维，学习问题分解、模式识别、抽象和算法设计",
    "objectives": [
        "理解计算思维的核心概念和方法",
        "掌握问题分解和模式识别的技巧"
    ],
    "knowledgeGraph": ""
}

manager.save_course_info(course_id, course_info)
```

### 4. 保存知识库文件

```python
# 读取文件
with open("document.pdf", "rb") as f:
    file_data = f.read()

# 保存文件
relative_path = manager.save_knowledge_base_file(
    course_id="computational-thinking",
    file_data=file_data,
    filename="计算思维导论.pdf"
)
```

### 5. 保存生成的教学资料

```python
material_data = {
    "id": "mat-001",
    "name": "递归算法详解",
    "type": "blog",
    "content": "...",
    "created_at": "2024-01-01T00:00:00",
    "file_extension": ".md"
}

# 保存资料（无附件）
manager.save_generated_material(
    course_id="computational-thinking",
    material_type="blog",
    material_id="mat-001",
    material_data=material_data
)

# 保存资料（带附件）
with open("content.md", "rb") as f:
    file_data = f.read()

manager.save_generated_material(
    course_id="computational-thinking",
    material_type="blog",
    material_id="mat-001",
    material_data=material_data,
    file_data=file_data
)
```

### 6. 获取课程信息

```python
# 获取课程基础信息
course_info = manager.get_course_info("computational-thinking")

# 获取知识库索引
kb_index = manager.get_knowledge_base_index("computational-thinking")

# 获取生成的教学资料
materials = manager.list_generated_materials(
    course_id="computational-thinking",
    material_type="blog"  # 可选，不指定则返回所有类型
)
```

### 7. 删除课程

```python
manager.delete_course("computational-thinking")
```

## API 参考

### CourseStorageManager 类

#### 方法说明

- `create_course_structure(course_id: str) -> Path`: 创建课程目录结构
- `save_course_info(course_id: str, course_info: Dict) -> bool`: 保存课程基础信息
- `get_course_info(course_id: str) -> Optional[Dict]`: 获取课程基础信息
- `save_knowledge_base_file(course_id: str, file_data: bytes, filename: str) -> Optional[str]`: 保存知识库文件
- `get_knowledge_base_index(course_id: str) -> List[Dict]`: 获取知识库索引
- `save_knowledge_base_index(course_id: str, index: List[Dict]) -> bool`: 保存知识库索引
- `save_generated_material(course_id: str, material_type: str, material_id: str, material_data: Dict, file_data: Optional[bytes]) -> bool`: 保存生成的教学资料
- `get_generated_material(course_id: str, material_type: str, material_id: str) -> Optional[Dict]`: 获取生成的教学资料
- `list_generated_materials(course_id: str, material_type: Optional[str]) -> List[Dict]`: 列出所有生成的教学资料
- `delete_course(course_id: str) -> bool`: 删除课程及其所有数据

## 数据格式

### course_info.json

```json
{
  "id": "computational-thinking",
  "title": "计算思维",
  "description": "课程简介",
  "objectives": [
    "教学目标1",
    "教学目标2"
  ],
  "knowledgeGraph": "知识图谱数据或URL"
}
```

### knowledge_base/index.json

```json
[
  {
    "id": "doc-1234567890",
    "filename": "计算思维导论.pdf",
    "path": "knowledge_base/documents/计算思维导论.pdf",
    "size": 1024000,
    "uploaded_at": "2024-01-01T00:00:00"
  }
]
```

### generated_materials/{type}/{material_id}.json

```json
{
  "id": "mat-001",
  "name": "资料名称",
  "type": "blog",
  "content": "资料内容",
  "created_at": "2024-01-01T00:00:00",
  "file_path": "generated_materials/blogs/mat-001.md"
}
```

## 注意事项

1. 所有文件路径使用UTF-8编码
2. JSON文件使用UTF-8编码，ensure_ascii=False以确保中文字符正确保存
3. 文件操作会自动创建必要的目录
4. 删除操作会递归删除整个课程目录，请谨慎使用
5. 建议在生产环境中定期备份 course_data 目录


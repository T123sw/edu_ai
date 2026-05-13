# RAG 系统支持的文件格式

## 当前支持的文件格式

### 1. PDF 文档 (.pdf)
- **描述**: 可移植文档格式
- **加载器**: PyMuPDFLoader
- **特点**: 
  - 支持页面提取
  - 保留页面元数据
  - 支持文本和图片提取

### 2. Word 文档
#### 2.1 .docx (推荐)
- **描述**: Microsoft Word 2007+ 格式
- **加载器**: Docx2txtLoader
- **依赖**: `docx2txt` 或 `python-docx`
- **特点**:
  - 直接提取文本内容
  - 跳过页面解析，直接分块
  - 支持格式化的文本提取

#### 2.2 .doc (旧格式)
- **描述**: Microsoft Word 97-2003 格式
- **加载器**: docx2txt 库直接处理
- **依赖**: `docx2txt`
- **特点**:
  - 需要额外的 docx2txt 库支持
  - 可能在某些情况下兼容性较差
  - 建议转换为 .docx 格式以获得更好的支持

### 3. 文本文档
#### 3.1 纯文本 (.txt)
- **描述**: 纯文本文件
- **加载器**: TextLoader
- **编码支持**: UTF-8, GBK, GB2312, UTF-8-sig
- **特点**:
  - 自动检测编码
  - 支持中文文档
  - 直接读取，无需解析

#### 3.2 Markdown (.md, .markdown)
- **描述**: Markdown 格式文档
- **加载器**: TextLoader
- **编码支持**: UTF-8, GBK, GB2312, UTF-8-sig
- **特点**:
  - 保留 Markdown 格式
  - 支持代码块、表格等
  - 适合技术文档和笔记

## 文件处理流程

### 通用流程
1. **文件上传** → 验证文件类型
2. **文件加载** → 根据文件类型选择加载器
3. **文本提取** → 提取文档内容
4. **语义分块** → 使用智能分块策略
5. **向量化** → 生成 embedding
6. **存储** → 保存到向量数据库

### 特殊处理
- **PDF**: 保留页面信息，支持页面级检索
- **Word/文本**: 跳过页面解析，直接分块
- **编码处理**: 自动检测和处理多种中文编码

## 依赖要求

### 必需依赖
```bash
# PDF 支持
pip install pymupdf>=1.23

# Word 支持
pip install docx2txt>=0.8
pip install python-docx>=1.0.0

# LangChain 支持
pip install langchain-core>=0.1
pip install langchain-community>=0.0.20
pip install langchain-text-splitters>=0.0.1
```

### 安装所有依赖
```bash
pip install -r requirements_api.txt
```

## 使用建议

### 推荐格式
1. **PDF** (.pdf) - 最佳兼容性，支持页面信息
2. **Word** (.docx) - 现代格式，完整支持
3. **Markdown** (.md) - 适合技术文档

### 注意事项
1. **.doc 格式**: 旧格式，建议转换为 .docx
2. **编码问题**: 确保文本文件使用 UTF-8 编码以获得最佳兼容性
3. **文件大小**: 建议单个文件不超过 50MB
4. **文件数量**: 建议每次导入不超过 100 个文件

## 错误处理

### 常见错误
1. **"No module named 'docx2txt'"**
   - 解决: `pip install docx2txt`

2. **"不支持的文件类型"**
   - 检查文件扩展名是否正确
   - 确认文件格式在支持列表中

3. **"编码错误"**
   - 尝试将文件转换为 UTF-8 编码
   - 或使用支持的编码格式（GBK, GB2312）

## 未来计划

### 计划支持
- Excel (.xls, .xlsx)
- PowerPoint (.ppt, .pptx)
- HTML (.html, .htm)
- RTF (.rtf)

### 改进方向
- OCR 支持（图片中的文字）
- 表格结构化提取
- 更好的格式保留


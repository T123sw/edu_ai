# 课程准备附件统一使用 MinerU

课程准备上传的 PDF、DOC/DOCX、PPT/PPTX、XLS/XLSX、PNG/JPG/JPEG/JP2/WebP/GIF/BMP、HTML 使用项目已有 MinerU Cloud v4 API。格式范围依据 [MinerU 官方 API 文档](https://mineru.net/apiManage/docs)（2026-09-18），不将本地开源 CLI 的格式支持范围视为云 API 能力。

TXT、MD、Markdown 仍由本地 UTF-8 读取。上传接口及前端文件选择器同步接受这些格式，保留 30 MB 限制。

## 处理方式

- 复用 `get_pdf_parser()` 的现有运行配置和密钥，无新增服务或密钥配置。
- MinerU 上传保留原始字节及真实扩展名，修复原先非 PDF 文件统一命名为 `document.pdf` 的问题；HTML 自动指定 `MinerU-HTML`，其他格式沿用配置模型。
- Word 不再经过 antiword、LibreOffice 或本地 DOCX 文本抽取。MinerU 失败报错，不静默降级为可能缺失表格与图片内容的本地结果。
- 继续保存文件哈希、文本定位和解析缺陷；PDF 保留预检查及页数覆盖校验，其他格式不虚构页码。
- 旧的三种本地 Word 解析缓存在下次读取时失效，成功后改存 MinerU 结果；正常 MinerU 缓存继续复用。已经完成的任务及其理解检查点不主动重跑。

## 验证与生效

- 针对性测试：36 passed、2 skipped，覆盖支持格式的原始字节路由、真实 HTTP 协议模拟、HTML 模型、失败传播、旧缓存替换、上传接口格式放行。
- 课程准备及共享 RAG 解析回归：252 passed、78 skipped；随后新增的上传接口测试单独通过。PostgreSQL 专项未配置独立库而跳过。
- 真实 API 使用合成 DOCX、PNG、HTML 文件，均通过，分别耗时约 10.14、5.00、4.99 秒。仅这三类做了真实远程验证，其余格式完成协议模拟测试。
- 前端生产构建通过，并发布到 `frontend/dist`，保留旧静态资源供已打开页面使用。
- 后端尚未重启：当前环境 sudo 要求密码。执行 `sudo systemctl restart edu-ai-backend` 后完整生效，不需要使用旧的激活脚本。

验证原始结果见 `artifacts/2026-09-18-preparation-mineru/`。

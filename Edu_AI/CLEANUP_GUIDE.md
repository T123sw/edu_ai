# 项目清理指南

本指南帮助您清理项目中不需要的文件和目录。

## 🗑️ 建议清理的内容

### 1. 备份目录（可删除）

以下目录是重复的备份，建议删除：

```bash
api/Edu_AI copy/
```

**操作**: 
- Windows: 可以手动删除或使用资源管理器
- 删除前请确认 `api/Edu_AI/` 目录中的代码是最新的

### 2. 临时测试文件（可删除）

以下临时文件可以删除：

```bash
api/Edu_AI/1.py
api/Edu_AI/text1.py
```

### 3. 重复的数据目录（需确认）

以下目录如果在根目录和 `api/Edu_AI/` 下都存在，需要确认哪个是正在使用的：

```bash
# 根目录下的这些目录（如果存在且未使用）
data/
enhanced_documents/
vector_db/
```

**注意**: 删除前请：
1. 确认 `api/Edu_AI/` 下的对应目录是主要使用的
2. 备份重要数据
3. 检查 `.gitignore` 确保这些目录已被忽略

### 4. Python缓存文件（会自动忽略）

以下文件/目录已在 `.gitignore` 中，git不会跟踪，但可以手动清理：

```bash
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
```

## ✅ 清理后的目录结构

清理后，项目结构应该更加清晰：

```
Edu_AI/
├── api/
│   └── Edu_AI/          # 唯一的后端目录（无copy目录）
│       ├── *.py         # 源代码文件（无临时文件）
│       ├── data/        # 数据目录
│       └── ...
├── src/                 # 前端代码
├── docs/                # 所有文档统一存放
├── public/              # 静态资源
└── 配置文件...
```

## 🔍 清理检查清单

- [ ] 删除 `api/Edu_AI copy/` 目录
- [ ] 删除临时文件 `1.py`, `text1.py`
- [ ] 检查并清理根目录下重复的数据目录（如存在）
- [ ] 确认 `.gitignore` 文件已正确配置
- [ ] 验证项目仍可正常启动和运行

## ⚠️ 注意事项

1. **备份重要数据**: 删除前请确保已备份重要数据
2. **测试项目**: 清理后请测试项目是否能正常运行
3. **Git提交**: 如果是Git仓库，建议先提交当前更改再清理

## 🛠️ 清理脚本（可选）

如需批量清理，可以使用以下PowerShell脚本：

```powershell
# 删除备份目录
Remove-Item -Path "api\Edu_AI copy" -Recurse -Force -ErrorAction SilentlyContinue

# 删除临时文件
Remove-Item -Path "api\Edu_AI\1.py" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "api\Edu_AI\text1.py" -Force -ErrorAction SilentlyContinue

# 清理Python缓存
Get-ChildItem -Path "api" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Write-Host "清理完成！"
```

**注意**: 请谨慎使用，建议先手动检查再执行。


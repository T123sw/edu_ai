# Edu AI PostgreSQL 本地环境

首次启动前，将 `.env.example` 复制为不会提交到 Git 的 `.env.postgres`，并同时修改 `POSTGRES_PASSWORD` 与 `DATABASE_URL` 中经过 URL 编码的密码。

通常直接启动 Edu AI 即可。`start_api.bat` 会检查 Docker、启动 PostgreSQL、等待健康状态并执行 Alembic 迁移：

```powershell
Set-Location .\Edu_AI\api\src
.\start_api.bat
```

只准备和验证数据库，不启动前端、后端和 OpenMAIC：

```powershell
.\start_api.bat --database-only
```

只检查项目与 PostgreSQL 配置，不启动任何服务：

```powershell
.\start_api.bat --check
```

也可以在仓库根目录手动管理数据库：

```powershell
docker compose --env-file .\infra\postgres\.env.postgres -f .\infra\postgres\compose.yml up -d
docker compose --env-file .\infra\postgres\.env.postgres -f .\infra\postgres\compose.yml ps
```

后端在宿主机运行时使用以下连接地址；`start_api.bat` 会从 `.env.postgres` 自动注入：

```dotenv
DATABASE_URL=postgresql+psycopg://edu_ai:<password>@127.0.0.1:5432/edu_ai
```

执行数据库结构迁移：

```powershell
Set-Location .\Edu_AI\api\src
python -m alembic upgrade head
```

先只读预览现有用户、课程和成员数据：

```powershell
python -m app.database.migrate_cli
```

确认预览数量后再导入；命令可重复执行，不会产生重复记录：

```powershell
python -m app.database.migrate_cli --apply
```

当前阶段导入不会切换业务读取路径，也不会修改或删除源 JSON。

停止容器但保留数据：

```powershell
docker compose --env-file .\infra\postgres\.env.postgres -f .\infra\postgres\compose.yml down
```

不要在有用数据时执行 `down -v`；该命令会删除数据库卷。

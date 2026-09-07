# Edu-AI Linux 启动、部署与数据迁移指南

适用环境：Ubuntu 22.04 x86_64，部署用户 `zxqs_ep`，代码目录 `/home/zxqs_ep/Edu_AI`。本指南只使用系统 PostgreSQL、系统级 systemd 和 Nginx，不要求 Docker。

## 当前服务器状态（2026-09-02）

生产服务已经安装为 systemd 服务，退出 VS Code 或关闭 SSH 后仍会继续运行。当前固定目录如下：

| 内容 | 绝对路径 |
| --- | --- |
| 项目代码 | `/home/zxqs_ep/Edu_AI` |
| 通用文件存储 | `/home/zxqs_ep/data/edu_ai/storage` |
| 课程文件 | `/home/zxqs_ep/data/edu_ai/course_data` |
| OpenMAIC 课堂数据 | `/home/zxqs_ep/data/edu_ai/openmaic` |
| 临时文件 | `/home/zxqs_ep/data/edu_ai/tmp` |
| 迁移备份 | `/home/zxqs_ep/data/Edu_AI_backups` |
| 环境配置 | `/home/zxqs_ep/Edu_AI/.env` |

PostgreSQL 中保存用户、课程、成员关系、材料、知识文档和学习记录等结构化数据。PostgreSQL 由系统服务管理，不应手工编辑其物理数据目录。

2026-09-02 已完成 Windows 本地真实数据迁移和文件路径切换。迁移后的基线包括 10 门课程、52 条课程成员关系、185 份材料、261 个知识文档和 7 个用户。原迁移包已按要求清除；迁移前、迁移后的可恢复备份均保留在 `/home/zxqs_ep/data/Edu_AI_backups/`。源电脑原本已有 227 个数据库引用文件缺失，迁移无法补回这些原始缺口。

## 日常启动（已部署服务器）

正常情况下服务随系统启动，无需打开 VS Code。先查看状态：

```bash
systemctl is-active postgresql edu-ai-openmaic edu-ai-backend nginx
```

四行均显示 `active` 时，直接在浏览器访问服务器地址即可。需要手动启动时执行：

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
bash scripts/start-production.sh
```

看到命令行前缀出现 `(edu-ai)` 后，表示当前运维终端已经进入项目环境。脚本会请求 `sudo` 密码，依次启动 PostgreSQL、OpenMAIC、FastAPI 和 Nginx，并等待健康检查通过。

生产服务本身不依赖当前终端持续激活 Conda。systemd 单元已经固定使用：

```text
/home/zxqs_ep/miniforge3/envs/edu-ai
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/pnpm
```

因此退出 Conda、关闭终端或退出 VS Code，不会终止已经启动的生产服务。需要执行 Alembic、诊断脚本或其他项目命令时，统一先运行：

```bash
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
cd /home/zxqs_ep/Edu_AI
```

常用运维命令：

```bash
# 重启应用服务
sudo systemctl restart edu-ai-openmaic edu-ai-backend

# 停止整套服务
sudo systemctl stop nginx edu-ai-backend edu-ai-openmaic postgresql

# 查看最近日志
journalctl -u edu-ai-openmaic -u edu-ai-backend -n 200 --no-pager
```

每次启动或重启后执行：

```bash
curl --fail http://127.0.0.1:3000/api/health
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1/backend/health
```

## 通过 SSH 端口映射在电脑浏览器访问前端

本项目当前通过 SSH 本地端口转发访问，不需要把服务器的 HTTP、FastAPI 或 OpenMAIC 端口开放到公网。以下命令必须在自己的电脑终端中执行，不是在服务器终端或 VS Code 远程终端中执行。

Windows PowerShell、Windows Terminal、macOS 和 Linux 均可使用系统自带的 OpenSSH：

```bash
ssh -N -L 8080:127.0.0.1:80 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 zxqs_ep@<服务器SSH地址>
```

如果 SSH 使用非默认端口，还需添加 `-p`：

```bash
ssh -N -p <SSH端口> -L 8080:127.0.0.1:80 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 zxqs_ep@<服务器SSH地址>
```

输入 SSH 密码或完成密钥认证后，终端没有继续输出是正常现象。保持该终端窗口运行，然后在同一台电脑的浏览器访问：

```text
http://127.0.0.1:8080/
```

此时请求路径为：

```text
电脑浏览器 127.0.0.1:8080
  -> SSH 加密隧道
  -> 服务器 127.0.0.1:80（Nginx）
  -> /backend 转发到 FastAPI 127.0.0.1:8001
```

注意事项：

1. `8080` 是电脑本地端口，可以换成其他未被占用的端口，例如 `18080`；修改后浏览器地址也要同步改为 `http://127.0.0.1:18080/`。
2. 不要把 `-L` 两侧写反。正确格式是 `电脑本地端口:服务器侧目标地址:服务器侧目标端口`，本项目固定映射到服务器的 `127.0.0.1:80`。
3. `-N` 表示只建立隧道、不打开远程 Shell。关闭该电脑终端、按 `Ctrl+C`、电脑休眠或 SSH 断线后，端口映射会消失，浏览器将无法继续访问；服务器上的 systemd 服务仍会运行。
4. 前端配置应保持 `VITE_API_BASE_URL=/backend`。浏览器的 API 请求会沿同一条 SSH 隧道进入 Nginx，无需再单独映射 `8001` 或 `3000`。
5. 只需要保证服务器 SSH 端口可访问；无需在云安全组或防火墙中开放 `80`、`3000`、`8001` 或 `5432`。
6. VS Code Remote SSH 也可能创建本地端口转发并占用 `8080`。如果退出 VS Code 后命令才成功，通常说明 VS Code 已占用该本地端口。可更换本地端口，或先关闭 VS Code 中对应的“端口/Ports”转发项。

在自己电脑上检查本地端口是否被占用：

```powershell
# Windows PowerShell
Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
```

```bash
# macOS / Linux
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

建立隧道后可在自己电脑的另一个终端验证：

```bash
curl http://127.0.0.1:8080/backend/health
```

如果 SSH 报 `Address already in use`，说明电脑本地 `8080` 已被占用，换用 `18080` 等端口。如果 SSH 已连接但浏览器打不开，先确认服务器上的服务状态和本机入口：

```bash
# 以下命令在服务器终端执行
systemctl is-active nginx edu-ai-backend edu-ai-openmaic
curl --fail http://127.0.0.1/backend/health
```

## 1. 安装系统组件

```bash
sudo apt update
sudo apt install -y git curl ca-certificates nginx postgresql postgresql-contrib
```

Playwright 的系统库在 Miniforge 环境创建后安装，见第 4 步。

## 2. 安装 Miniforge

```bash
curl -L -o /tmp/Miniforge3.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/Miniforge3.sh -b -p /home/zxqs_ep/miniforge3
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda init bash
```

重新打开终端后，`conda --version` 应能正常输出。

## 3. 放置代码与数据目录

```bash
cd /home/zxqs_ep
git clone <repository-url> Edu_AI
cd Edu_AI

install -d -m 750 \
  /home/zxqs_ep/data/edu_ai/storage \
  /home/zxqs_ep/data/edu_ai/course_data \
  /home/zxqs_ep/data/edu_ai/openmaic \
  /home/zxqs_ep/data/edu_ai/tmp \
  /home/zxqs_ep/data/edu_ai/models \
  /home/zxqs_ep/data/edu_ai/logs \
  /home/zxqs_ep/data/edu_ai/backups/postgres
```

将 `<repository-url>` 替换为实际远程仓库地址。运行数据不通过 Git 传输，迁移规则见 [`运行时数据边界.md`](运行时数据边界.md)。

## 4. 创建统一环境

```bash
cd /home/zxqs_ep/Edu_AI
bash scripts/install-all.sh
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai

# 安装 Chromium 在 Ubuntu 上需要的系统库
sudo env "PATH=$PATH" pnpm --dir openmaic-sidecar exec playwright install-deps chromium
```

安装脚本使用根目录 `environment.yml`，统一安装 Python 3.12、Node.js 22、pnpm 10.28、FFmpeg/ffprobe 6+、后端依赖、两个 Node 项目和 Chromium。

验证版本：

```bash
python --version
node --version
pnpm --version
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
```

## 5. 初始化 PostgreSQL

按 [`deploy/postgres/README.md`](../../deploy/postgres/README.md) 创建 `edu_ai` 用户和数据库。数据库只监听 `127.0.0.1:5432`。

## 6. 配置环境

安装脚本首次运行会复制 `.env.example` 为 `.env`。编辑根目录唯一配置文件：

```bash
cd /home/zxqs_ep/Edu_AI
chmod 600 .env
nano .env
```

必须至少填写 `DATABASE_URL` 和实际使用的模型 API Key。生产构建保持：

```dotenv
VITE_API_BASE_URL=/backend
OPENMAIC_BASE_URL=http://127.0.0.1:3000
CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1
```

当前服务器的文件运行目录必须配置为：

```dotenv
STORAGE_ROOT=/home/zxqs_ep/data/edu_ai/storage
COURSE_STORAGE_ROOT=/home/zxqs_ep/data/edu_ai/course_data
TEMP_DIR=/home/zxqs_ep/data/edu_ai/tmp
OPENMAIC_DATA_ROOT=/home/zxqs_ep/data/edu_ai/openmaic
```

不要改回 `/data/edu_ai/`，也不要把密钥写入 systemd、Nginx 或文档。

## 7. 执行迁移与生产构建

```bash
cd /home/zxqs_ep/Edu_AI
conda activate edu-ai

cd backend/src
python -m alembic upgrade head
cd ../..

bash scripts/build-production.sh
```

构建结果应为 `frontend/dist/` 和 `openmaic-sidecar/.next/`。

## 8. 安装 systemd 与 Nginx

```bash
cd /home/zxqs_ep/Edu_AI
sudo install -m 644 deploy/systemd/edu-ai-openmaic.service /etc/systemd/system/
sudo install -m 644 deploy/systemd/edu-ai-backend.service /etc/systemd/system/
sudo install -m 644 deploy/nginx/edu-ai.conf /etc/nginx/sites-available/edu-ai.conf
sudo ln -sfn /etc/nginx/sites-available/edu-ai.conf /etc/nginx/sites-enabled/edu-ai.conf
sudo rm -f /etc/nginx/sites-enabled/default

sudo systemd-analyze verify \
  /etc/systemd/system/edu-ai-openmaic.service \
  /etc/systemd/system/edu-ai-backend.service
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now edu-ai-openmaic edu-ai-backend nginx
```

安装完成后，也可以使用仓库脚本统一启动 PostgreSQL、OpenMAIC、FastAPI 与承载前端的 Nginx，脚本会等待服务就绪并执行健康检查：

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
bash scripts/start-production.sh
```

这里的 `rm -f` 只删除 Ubuntu 的 Nginx 默认站点软链接，不删除项目或用户数据。

## 9. 验收

```bash
systemctl is-active postgresql edu-ai-openmaic edu-ai-backend nginx
curl --fail http://127.0.0.1:3000/api/health
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1/backend/health
```

浏览器访问服务器的 HTTP 地址后，再验证登录、课程列表、知识库检索、AI 课堂生成、OpenMAIC 播放、PPTX 导出和视频导出。若失败，查看：

```bash
journalctl -u edu-ai-openmaic -u edu-ai-backend -n 200 --no-pager
sudo tail -n 200 /var/log/nginx/error.log
```

正式域名与 HTTPS 尚未确定，因此当前 Nginx 配置以 IP/任意主机名接入。确认域名后再单独配置证书和 443，不要在本轮仓库清理中开放额外端口。

## 10. 数据备份与回滚

本次迁移留下两个基线备份：

```text
/home/zxqs_ep/data/Edu_AI_backups/migration-precutover-20260902T064000Z
/home/zxqs_ep/data/Edu_AI_backups/migration-postcutover-20260902T064500Z
```

其中 `migration-postcutover-20260902T064500Z` 是迁移完成后的恢复基线，包含：

- `edu_ai_migrated.dump`：PostgreSQL 逻辑备份；
- `course_data_migrated.tar.gz`：课程文件；
- `openmaic_migrated.tar.gz`：OpenMAIC 文件；
- `SHA256SUMS`：完整性校验；
- `audit/`：迁移清单与盘点报告。

校验备份：

```bash
cd /home/zxqs_ep/data/Edu_AI_backups/migration-postcutover-20260902T064500Z
sha256sum -c SHA256SUMS
```

恢复会覆盖正式数据库和运行文件，必须先停止应用写入并再次备份当前状态。不要在服务运行时直接执行 `pg_restore` 或解压覆盖；需要回滚时按本节备份内容制定恢复窗口。

旧目录 `/data/edu_ai` 当前仅作为临时回滚副本保留，不再是应用读写位置。确认新路径长期运行稳定后，再由管理员单独决定是否清理，启动操作不得自动删除它。

## 相关资料

- [`../operations/2026-09-02-real-data-migration.md`](../operations/2026-09-02-real-data-migration.md)
- [`服务器Codex部署交接.md`](服务器Codex部署交接.md)
- [`Linux服务器部署事实与待办.md`](Linux服务器部署事实与待办.md)
- [`运行时数据边界.md`](运行时数据边界.md)
- [`../../DEPENDENCIES.md`](../../DEPENDENCIES.md)

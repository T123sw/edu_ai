# Edu-AI Linux 服务器迁移部署交接实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. If that skill is unavailable, execute the checkbox steps manually and stop at every checkpoint.

**Goal:** 将远程仓库 `main` 的 Edu-AI 安全迁移到 Ubuntu 22.04 服务器，并先完成 Miniforge、`edu-ai` Conda 环境和项目依赖安装验证，再分阶段完成数据目录、PostgreSQL、生产构建、systemd、Nginx 与功能验收。

**Architecture:** 代码固定在 `/home/zxqs_ep/Edu_AI`，运行数据固定在 `/data/edu_ai`。FastAPI、OpenMAIC 和 PostgreSQL 只监听回环地址，由 Nginx 提供唯一外部入口；部署不使用 Docker，也不在首轮部署本地 GPU 模型。

**Tech Stack:** Ubuntu 22.04、Miniforge/Conda、Python 3.12、Node.js 22、pnpm 10.28、FFmpeg 6+、PostgreSQL、systemd、Nginx、Playwright Chromium。

---

## 1. 给服务器 Codex 的执行边界

首次接手时只执行本文的“任务 1～4”，完成 Conda 环境与项目依赖验证后必须停止并汇报，不得自行继续初始化数据库、填写密钥、安装 systemd 服务或切换流量。

执行过程中遵守以下约束：

- 先阅读仓库根目录 `AGENTS.md`、`项目总览地图.md`、`docs/deployment/README.md` 和本文。
- 每个任务逐项记录命令、退出码和关键结果；任一步失败立即停止，不猜测、不绕过验证。
- 不在对话、日志、Git 提交或命令输出中展示服务器密码、数据库密码和 API Key。
- 不修改或删除服务器上已有目录、数据库、服务和用户数据；遇到同名资源时先只读检查并汇报。
- 不安装 Docker，不部署 EduAgent、SearXNG、HTML2PPT、普通 PPT 服务、数字人、LiveTalking 或 WebRTC。
- 不开放公网端口 `3000`、`5432`、`8001`；首轮也不修改防火墙、Nginx 和 systemd。
- 不安装或升级 NVIDIA 驱动、CUDA 和本地大模型；首轮继续使用远程模型 API。
- 只从远程仓库 `main` 部署，不在服务器上直接修改产品代码。

## 2. 已确认的服务器与项目事实

| 项目 | 已确认事实 |
| --- | --- |
| 服务器 | Ubuntu 22.04.5 LTS，x86_64，主机名 `server163` |
| 账号 | `zxqs_ep`，属于 `sudo` 组，sudo 需要交互输入密码 |
| 资源 | 40 逻辑 CPU、250 GiB 内存、`/data` 约 3.1 TiB 可用 |
| GPU | 2 张 RTX 3090 24 GiB，驱动 535.309.01，CUDA 12.2 |
| 当前工具 | Git、curl、GCC/G++、Make 已安装 |
| 当前缺失 | Conda/Mamba、Node.js、pnpm、FFmpeg/ffprobe、Docker |
| 代码目录 | `/home/zxqs_ep/Edu_AI` |
| 数据目录 | `/data/edu_ai` |
| Git 仓库 | `https://github.com/T123sw/edu_ai.git`，部署分支 `main` |
| 内部端口 | OpenMAIC `3000`、PostgreSQL `5432`、FastAPI `8001` |
| 外部入口 | Nginx `80`；域名与 HTTPS 尚未确定 |

## 3. 文件职责

- `environment.yml`：唯一 Conda 环境定义。
- `scripts/install-all.sh`：创建或更新 `edu-ai` 环境，安装 Python、前端、OpenMAIC 与 Playwright 项目依赖。
- `.env.example`：服务器根目录 `.env` 的无密钥模板。
- `scripts/build-production.sh`：构建 `frontend/dist` 和 `openmaic-sidecar/.next`。
- `deploy/postgres/README.md`：PostgreSQL 建库约定。
- `deploy/systemd/*.service`：后端与 OpenMAIC 系统服务。
- `deploy/nginx/edu-ai.conf`：Nginx 静态文件与 `/backend/` 反向代理配置。
- `docs/deployment/运行时数据边界.md`：代码、运行数据与备份的边界。

## 4. 第一轮：环境交接任务

### 任务 1：只读预检

- [ ] **步骤 1：确认登录身份、系统和磁盘，不输出任何密钥**

```bash
whoami
hostname
cat /etc/os-release
uname -m
df -h /home /data
free -h
```

预期：用户为 `zxqs_ep`，系统为 Ubuntu 22.04、架构为 `x86_64`，`/home` 与 `/data` 有足够空间。

- [ ] **步骤 2：确认目标端口当前状态**

```bash
ss -ltn | grep -E ':(80|3000|5432|8001)\b' || true
```

预期：记录实际结果即可。若端口已被未知服务占用，第一轮不结束进程、不改配置，只在汇报中列出。

- [ ] **步骤 3：确认关键下载地址可访问**

```bash
curl -IfsS --max-time 20 https://github.com/ >/dev/null
curl -IfsS --max-time 20 https://conda.anaconda.org/conda-forge/ >/dev/null
```

预期：两条命令退出码均为 `0`。失败时停止，报告域名、错误和退出码，不临时改用不明镜像。

### 任务 2：安装或复用 Miniforge

- [ ] **步骤 1：只读检查目标安装目录**

```bash
if [ -x /home/zxqs_ep/miniforge3/bin/conda ]; then
  echo "Miniforge already installed"
elif [ -e /home/zxqs_ep/miniforge3 ]; then
  echo "BLOCKED: /home/zxqs_ep/miniforge3 exists but conda is incomplete"
  exit 1
else
  echo "Miniforge is not installed"
fi
```

预期：目录不存在，或者已有可执行的 Conda。若存在不完整目录，停止并汇报，不删除目录。

- [ ] **步骤 2：仅在尚未安装时下载并安装官方 Miniforge**

```bash
if [ ! -x /home/zxqs_ep/miniforge3/bin/conda ]; then
  curl -fL --retry 3 -o /tmp/Miniforge3.sh \
    https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
  bash /tmp/Miniforge3.sh -b -p /home/zxqs_ep/miniforge3
fi
```

预期：安装器退出码为 `0`，`/home/zxqs_ep/miniforge3/bin/conda` 存在。

- [ ] **步骤 3：加载 Conda 并初始化当前用户的 Bash**

```bash
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda --version
conda init bash
```

预期：能够输出 Conda 版本；`conda init` 只修改 `zxqs_ep` 自己的 Bash 配置。

### 任务 3：获取并核对部署代码

- [ ] **步骤 1：安全处理目标代码目录**

```bash
cd /home/zxqs_ep
if [ -d Edu_AI/.git ]; then
  echo "Existing Git checkout found"
elif [ -e Edu_AI ]; then
  echo "BLOCKED: /home/zxqs_ep/Edu_AI exists but is not a Git checkout"
  exit 1
else
  git clone https://github.com/T123sw/edu_ai.git Edu_AI
fi
```

预期：得到 `/home/zxqs_ep/Edu_AI/.git`。若同名非 Git 目录存在，停止，不移动、不覆盖。

- [ ] **步骤 2：只接受 `main` 的快进同步并确认工作区干净**

```bash
cd /home/zxqs_ep/Edu_AI
git fetch --prune origin
git checkout main
git pull --ff-only origin main
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

预期：`HEAD` 与 `origin/main` 完全相同，`git status --short` 没有文件变更。存在本地修改、分叉或合并需求时停止并汇报。

- [ ] **步骤 3：执行仓库自带的部署一致性检查**

```bash
cd /home/zxqs_ep/Edu_AI
python3 scripts/check-deployment-consistency.py
```

预期：输出 `Deployment consistency check passed.`。

### 任务 4：创建 `edu-ai` Conda 环境并安装项目依赖

- [ ] **步骤 1：使用仓库脚本创建环境，第一轮暂不安装浏览器**

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
bash scripts/install-all.sh --skip-browsers
```

预期：脚本退出码为 `0`；创建或更新名为 `edu-ai` 的环境，安装两个 Node 项目依赖，并在根目录首次创建权限为 `600` 的 `.env` 模板。

- [ ] **步骤 2：验证统一版本基线**

```bash
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
python --version
node --version
pnpm --version
ffmpeg -version | head -n 1
ffprobe -version | head -n 1
```

预期：Python `3.12.x`、Node.js `22.x`、pnpm `10.28.x`、FFmpeg/ffprobe `6` 或更新版本。

- [ ] **步骤 3：验证后端核心依赖可以导入**

```bash
conda run --no-capture-output -n edu-ai \
  python -c "import fastapi, uvicorn, psycopg; print('backend imports passed')"
```

预期：输出 `backend imports passed`，退出码为 `0`。

- [ ] **步骤 4：验证配置文件权限且不显示配置内容**

```bash
cd /home/zxqs_ep/Edu_AI
test -f .env
stat -c '%a %U:%G %n' .env
git status --short --branch
```

预期：`.env` 权限为 `600`、所有者为 `zxqs_ep`；`.env` 和依赖目录均未进入 Git 状态。

- [ ] **步骤 5：到达第一轮强制检查点并停止**

服务器 Codex 必须向用户汇报以下内容，然后等待明确授权：

```text
第一轮环境交接报告
- 主机/账号：
- Git HEAD：
- 工作区是否干净：
- Miniforge/Conda 版本：
- Python/Node/pnpm/FFmpeg 版本：
- 后端核心导入：通过/失败
- .env 是否存在且权限为 600：
- 80/3000/5432/8001 端口占用：
- GitHub/conda-forge 连通性：
- 警告或阻塞项：
- 未执行事项：浏览器依赖、数据目录、PostgreSQL、密钥、迁移、构建、systemd、Nginx、业务验收
```

报告中不得粘贴 `.env` 内容、密码或 API Key。

## 5. 第二轮及后续任务（需用户逐阶段授权）

### 任务 5：创建运行数据目录并安装 Playwright Chromium

- [ ] **步骤 1：创建并核验运行目录**

```bash
sudo install -d -o zxqs_ep -g zxqs_ep -m 750 \
  /data/edu_ai \
  /data/edu_ai/storage \
  /data/edu_ai/course_data \
  /data/edu_ai/openmaic \
  /data/edu_ai/tmp \
  /data/edu_ai/models \
  /data/edu_ai/logs \
  /data/edu_ai/backups/postgres
find /data/edu_ai -maxdepth 2 -type d -printf '%m %u:%g %p\n' | sort
```

预期：列出的目录所有者为 `zxqs_ep:zxqs_ep`，权限为 `750`。已有目录权限或所有者不一致时先汇报，不递归改写其中已有数据。

- [ ] **步骤 2：安装 Chromium 系统库与浏览器二进制**

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
sudo env "PATH=$PATH" pnpm --dir openmaic-sidecar exec playwright install-deps chromium
pnpm --dir openmaic-sidecar exec playwright install chromium
pnpm --dir frontend exec playwright install chromium
pnpm --dir openmaic-sidecar exec playwright --version
```

预期：所有安装命令退出码为 `0`，最后输出 Playwright 版本。

- [ ] **步骤 3：重新确认空间与 Git 边界**

```bash
df -h /home /data
du -sh /home/zxqs_ep/miniforge3 /home/zxqs_ep/Edu_AI /data/edu_ai
cd /home/zxqs_ep/Edu_AI
git status --short --branch
```

预期：空间足够，Git 工作区没有新增的已跟踪变更。

执行依据：`docs/deployment/README.md` 第 3～4 节。

### 任务 6：初始化 PostgreSQL

- [ ] **步骤 1：安装并启动 Ubuntu PostgreSQL 系统服务**

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
systemctl is-active postgresql
```

预期：最后输出 `active`。

- [ ] **步骤 2：安全创建数据库角色**

```bash
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='edu_ai'" | grep -q 1; then
  echo "PostgreSQL role edu_ai already exists; stop for ownership review"
  exit 3
else
  sudo -u postgres createuser --pwprompt edu_ai
fi
```

预期：如果角色不存在，由用户在终端交互式输入新密码；服务器 Codex 不得索取或转述密码。如果角色已经存在，先停止并核对它是否属于本项目，不自动改密码。

- [ ] **步骤 3：仅在角色归属确认后创建数据库**

```bash
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='edu_ai'" | grep -q 1; then
  sudo -u postgres psql -tAc "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE datname='edu_ai'"
  sudo -u postgres psql -d edu_ai -c '\conninfo'
else
  sudo -u postgres createdb --owner=edu_ai edu_ai
  sudo -u postgres psql -d edu_ai -c '\conninfo'
fi
```

预期：数据库 `edu_ai` 存在且所有者符合预期。已有数据库不删除、不清空。

- [ ] **步骤 4：确认监听范围**

```bash
sudo -u postgres psql -tAc "SHOW listen_addresses;"
ss -ltn | grep ':5432\b'
```

预期：PostgreSQL 只监听本机地址，不出现 `0.0.0.0:5432` 或 `[::]:5432`。

执行依据：`deploy/postgres/README.md`。如果服务器已经存在同名用户或数据库，先只读检查，不删除、不重建。

### 任务 7：由用户安全填写生产配置

- [ ] **步骤 1：用户在服务器终端直接编辑根目录唯一 `.env`**

```bash
cd /home/zxqs_ep/Edu_AI
chmod 600 .env
nano .env
```

用户填写 URL 编码后的数据库密码和实际使用的 API Key。服务器 Codex在编辑期间暂停，不要求用户把密钥发送到聊天中。

- [ ] **步骤 2：在不输出值的情况下验证结构配置**

```bash
cd /home/zxqs_ep/Edu_AI
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
from pathlib import Path

required = {
    "DATABASE_URL": None,
    "VITE_API_BASE_URL": "/backend",
    "OPENMAIC_BASE_URL": "http://127.0.0.1:3000",
    "CLASSROOM_VIDEO_FRONTEND_URL": "http://127.0.0.1",
    "STORAGE_ROOT": "/data/edu_ai/storage",
    "COURSE_STORAGE_ROOT": "/data/edu_ai/course_data",
    "TEMP_DIR": "/data/edu_ai/tmp",
    "OPENMAIC_DATA_ROOT": "/data/edu_ai/openmaic",
}
values = {}
for raw in Path(".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")

errors = []
for key, expected in required.items():
    value = values.get(key, "")
    if not value or "replace_with" in value:
        errors.append(f"{key}: missing")
    elif expected is not None and value != expected:
        errors.append(f"{key}: unexpected value")

for key in ("OPENROUTER_API_KEY", "QWEN_API_KEY", "OPENAI_API_KEY", "BOCHA_API_KEY", "TAVILY_API_KEY"):
    print(f"{key}: {'set' if values.get(key) else 'not set'}")

if errors:
    raise SystemExit("configuration validation failed: " + ", ".join(errors))
print("non-secret deployment configuration passed")
PY
```

预期：结构字段检查通过；API Key 只显示 `set` 或 `not set`。深度搜索需要 `BOCHA_API_KEY`，网页抽取按需配置 `TAVILY_API_KEY`，具体模型能力对应的 Key 必须在业务验收前设置。

### 任务 8：数据库迁移和生产构建

- [ ] **步骤 1：执行数据库迁移并核对 Alembic head**

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
cd backend/src
python -m alembic heads
python -m alembic upgrade head
python -m alembic current
cd ../..
```

预期：迁移退出码为 `0`，`current` 指向仓库的唯一 head。

- [ ] **步骤 2：执行两个生产构建并核对产物**

```bash
cd /home/zxqs_ep/Edu_AI
bash scripts/build-production.sh
test -f frontend/dist/index.html
test -f openmaic-sidecar/.next/BUILD_ID
git status --short --branch
```

预期：构建脚本退出码为 `0`，两个文件均存在，构建产物没有进入 Git 状态。

### 任务 9：安装 systemd 与 Nginx

- [ ] **步骤 1：安装 Nginx 并验证静态文件读取权限**

```bash
sudo apt update
sudo apt install -y nginx
namei -l /home/zxqs_ep/Edu_AI/frontend/dist/index.html
sudo -u www-data test -r /home/zxqs_ep/Edu_AI/frontend/dist/index.html
```

预期：`www-data` 可以读取 `index.html`。失败时停止并报告 `namei` 输出，不擅自对 `/home/zxqs_ep` 执行递归放权。

- [ ] **步骤 2：安装项目提供的 systemd 与 Nginx 配置**

```bash
cd /home/zxqs_ep/Edu_AI
sudo install -m 644 deploy/systemd/edu-ai-openmaic.service /etc/systemd/system/
sudo install -m 644 deploy/systemd/edu-ai-backend.service /etc/systemd/system/
sudo install -m 644 deploy/nginx/edu-ai.conf /etc/nginx/sites-available/edu-ai.conf
sudo ln -sfn /etc/nginx/sites-available/edu-ai.conf /etc/nginx/sites-enabled/edu-ai.conf
if [ -L /etc/nginx/sites-enabled/default ]; then
  sudo rm -f /etc/nginx/sites-enabled/default
elif [ -e /etc/nginx/sites-enabled/default ]; then
  echo "BLOCKED: default Nginx site is not a symlink"
  exit 1
fi
```

预期：仅移除 Ubuntu 默认站点软链接；如果同名路径不是软链接则停止。

- [ ] **步骤 3：先验证配置，再启用服务**

```bash
sudo systemd-analyze verify \
  /etc/systemd/system/edu-ai-openmaic.service \
  /etc/systemd/system/edu-ai-backend.service
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now edu-ai-openmaic edu-ai-backend nginx
systemctl is-active edu-ai-openmaic edu-ai-backend nginx
```

预期：两个配置验证命令退出码为 `0`，三个服务均为 `active`。

- [ ] **步骤 4：确认监听边界**

```bash
ss -ltn | grep -E ':(80|3000|5432|8001)\b'
```

预期：`80` 为 Nginx 外部入口；`3000`、`5432`、`8001` 只绑定本机地址。

### 任务 10：健康检查与业务验收

- [ ] **步骤 1：验证服务和三个健康入口**

```bash
systemctl is-active postgresql edu-ai-openmaic edu-ai-backend nginx
curl --fail --show-error http://127.0.0.1:3000/api/health
curl --fail --show-error http://127.0.0.1:8001/health
curl --fail --show-error http://127.0.0.1/backend/health
```

预期：四个服务均为 `active`，三次请求退出码均为 `0`。

- [ ] **步骤 2：逐项执行产品验收**

依次验证登录、普通对话、深度搜索、资料生成、课程与知识库、AI 课堂生成、OpenMAIC 播放、PPTX 导出和视频导出。每项必须记录为“通过”“失败”或“未配置”，附脱敏后的错误摘要；不得因健康接口通过就宣称全部业务通过。

- [ ] **步骤 3：失败时收集脱敏日志**

```bash
systemctl status edu-ai-openmaic edu-ai-backend nginx --no-pager
journalctl -u edu-ai-openmaic -u edu-ai-backend -n 200 --no-pager
sudo tail -n 200 /var/log/nginx/error.log
```

输出交给用户前必须检查并遮蔽令牌、密钥和含凭据的连接 URL。

### 任务 11：运行数据迁移与切换

本任务不在服务器环境部署计划中直接执行。Windows 数据源路径、数据库类型、数据规模、允许停机窗口和传输方式尚未确认，因此必须另建数据迁移计划。开始前由用户明确这五项输入，并按 `docs/deployment/运行时数据边界.md` 完成只读盘点、备份、文件数量与大小核对、数据库记录数核对和抽样哈希；不得使用 Git 传输真实运行数据，新服务器稳定前不得删除 Windows 原始副本。

## 6. 回滚与故障报告原则

- 环境安装失败：保留失败输出，停止后续步骤；不删除 Miniforge 或 Conda 环境，除非用户确认。
- Git 不一致：记录 `git status --short --branch`、`git rev-parse HEAD` 和 `git rev-parse origin/main`；不执行强制重置。
- 构建失败：不安装或重启服务，保留旧服务状态。
- systemd/Nginx 验证失败：不 enable、不 reload、不切换流量。
- 健康检查失败：记录对应服务的 `systemctl status` 和最近日志，但先对日志中的 URL、令牌和密钥做脱敏。
- 数据迁移校验失败：停止切换，继续使用原数据源，保留两端副本。

## 7. 完成定义

只有以下条件全部满足，才能把 Linux 代码与服务部署标记为完成：

- [ ] 远程 `main`、服务器 `HEAD` 和交接基线一致，服务器工作区无产品代码修改。
- [ ] Conda 与所有版本基线通过。
- [ ] PostgreSQL 迁移到 Alembic head。
- [ ] 前端和 OpenMAIC 生产构建成功。
- [ ] systemd 与 Nginx 配置验证成功，服务重启后仍可用。
- [ ] 三个健康接口通过。
- [ ] 用户指定的核心业务逐项验收并留下结果。
- [ ] 回滚来源、备份位置和未解决风险均已记录。

真实业务数据迁移和正式切换是独立里程碑：只有任务 11 的独立计划完成数量、大小、记录数和抽样哈希核对后，才能标记为迁移完成。

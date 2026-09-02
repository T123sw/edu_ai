# Edu-AI Linux 部署指南

适用环境：Ubuntu 22.04 x86_64，部署用户 `zxqs_ep`，代码目录 `/home/zxqs_ep/Edu_AI`。本指南只使用系统 PostgreSQL、系统级 systemd 和 Nginx，不要求 Docker。

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

sudo install -d -o zxqs_ep -g zxqs_ep -m 750 \
  /data/edu_ai/storage \
  /data/edu_ai/course_data \
  /data/edu_ai/openmaic \
  /data/edu_ai/tmp \
  /data/edu_ai/models \
  /data/edu_ai/logs \
  /data/edu_ai/backups/postgres
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

所有运行目录都应指向 `/data/edu_ai/`；不要把密钥写入 systemd 或 Nginx 文件。

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

## 相关资料

- [`服务器Codex部署交接.md`](服务器Codex部署交接.md)
- [`Linux服务器部署事实与待办.md`](Linux服务器部署事实与待办.md)
- [`运行时数据边界.md`](运行时数据边界.md)
- [`../../DEPENDENCIES.md`](../../DEPENDENCIES.md)

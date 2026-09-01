# PostgreSQL 系统服务

Linux 生产部署使用 Ubuntu 自带的 PostgreSQL 系统服务，不依赖 Docker。数据库仅监听本机 `127.0.0.1:5432`，应用通过根目录 `.env` 中的 `DATABASE_URL` 连接。

首次安装与建库：

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres createuser --pwprompt edu_ai
sudo -u postgres createdb --owner=edu_ai edu_ai
```

`createuser` 会交互式要求设置密码。随后将同一密码进行 URL 编码，写入 `/home/zxqs_ep/Edu_AI/.env`：

```dotenv
DATABASE_URL=postgresql+psycopg://edu_ai:<url-encoded-password>@127.0.0.1:5432/edu_ai
```

验证连接并执行结构迁移：

```bash
sudo -u postgres psql -d edu_ai -c '\conninfo'
cd /home/zxqs_ep/Edu_AI/backend/src
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m alembic upgrade head
```

systemd 后端服务也会在每次启动前安全地执行 `alembic upgrade head`。数据库备份必须写到 `/data/edu_ai/backups/postgres/`，不要写入代码仓库。

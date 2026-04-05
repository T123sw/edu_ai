# Edu-AI Linux Server Deployment Guide

This guide targets a single Linux server with:

- `nginx` serving the frontend static build
- `systemd` managing the FastAPI backend
- frontend and backend deployed on the same machine

## 1. Required files

You need these project files on the server:

- `package.json`
- `package-lock.json`
- `vite.config.ts`
- `src/`
- `public/`
- `index.html`
- `.env.production` based on `.env.production.example`
- `api/Edu_AI/app/`
- `api/Edu_AI/core/`
- `api/Edu_AI/new_rag/`
- `api/Edu_AI/local_video_ingestion.py`
- `api/Edu_AI/requirements.txt`
- `api/Edu_AI/requirements_api.txt`
- `api/Edu_AI/.env` based on `.env.production.example`

You also need these deployment templates from the repo:

- `deploy/systemd/edu-ai-backend.service`
- `deploy/nginx/edu-ai.conf`

## 2. Server packages

Install system packages first:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx ffmpeg
```

If your distro ships an old Node.js, install Node 20 separately before building the frontend.

## 3. Recommended server layout

```text
/srv/edu-ai/
├── backend/
│   ├── api/Edu_AI/
│   ├── course_data/
│   └── storage/
└── frontend/
    └── dist/
```

## 4. Backend setup

Upload the backend code under `/srv/edu-ai/backend/`, then run:

```bash
cd /srv/edu-ai/backend/api/Edu_AI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements_api.txt
```

Create the runtime env file:

```bash
cp .env.production.example .env
```

Then edit `.env` and fill at least:

- `JWT_SECRET_KEY`
- `CORS_ALLOW_ORIGINS`
- one usable LLM provider key and base URL
- one usable embedding provider key and base URL
- storage paths if you do not want the defaults from the template

## 5. Frontend setup

Upload the frontend code under `/srv/edu-ai/frontend-src/` or any build directory you prefer:

```bash
cd /srv/edu-ai/frontend-src
cp .env.production.example .env.production
npm install
npm run build
```

After the build:

```bash
sudo mkdir -p /srv/edu-ai/frontend
sudo cp -r dist /srv/edu-ai/frontend/
```

## 6. systemd setup

Copy the service file:

```bash
sudo cp deploy/systemd/edu-ai-backend.service /etc/systemd/system/
```

If needed, edit these fields before enabling it:

- `User`
- `Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable edu-ai-backend
sudo systemctl start edu-ai-backend
sudo systemctl status edu-ai-backend
```

## 7. nginx setup

Copy the nginx site config:

```bash
sudo cp deploy/nginx/edu-ai.conf /etc/nginx/sites-available/edu-ai
sudo ln -s /etc/nginx/sites-available/edu-ai /etc/nginx/sites-enabled/edu-ai
```

Edit these fields first:

- `server_name`
- `root`

Then test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 8. Health checks

Check backend directly:

```bash
curl http://127.0.0.1:8000/health
```

Check external access after nginx:

```bash
curl http://your-domain.com/health
```

Open:

- `http://your-domain.com`
- `http://your-domain.com/docs`

## 9. Notes

- The frontend currently expects `VITE_API_BASE_URL` to point to the same domain, for example `https://your-domain.com`.
- The codebase contains both `/api/...` routes and legacy root-level routes such as `/chat`, `/models`, `/health`, `/teacher/...`, and `/agent/...`, so the nginx config proxies all of them.
- Video ingestion requires both Python packages and the system `ffmpeg` binary.
- This guide does not yet include HTTPS. Add `certbot` or your preferred TLS setup after HTTP is working.

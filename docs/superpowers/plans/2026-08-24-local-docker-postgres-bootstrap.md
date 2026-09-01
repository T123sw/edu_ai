# Local Docker PostgreSQL Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the local Edu AI runtime dependencies, create an empty PostgreSQL 17 database in Docker, apply the current schema, and leave the application stack running and verified.

**Architecture:** The FastAPI backend, Vite frontend, and OpenMAIC sidecar run as host processes. PostgreSQL runs in Docker and persists its data in the named volume `edu_ai_postgres_data`; the host backend connects through `127.0.0.1:5432` using a Git-ignored environment file.

**Tech Stack:** Windows PowerShell, Python 3.12, FastAPI/Uvicorn, Node.js/npm, pnpm 10, Vite, OpenMAIC, Docker Desktop/Compose, PostgreSQL 17, Alembic, Playwright, FFmpeg

---

## Runtime File Map

- Create: `deploy/postgres/.env.postgres` — ignored PostgreSQL credentials and host connection URL.
- Create: `backend/src/.venv/` — ignored backend Python environment used automatically by `start_api.bat`.
- Refresh: `Edu_AI/node_modules/` — frontend packages installed from `package-lock.json` by the repository installer.
- Refresh: `openmaic-sidecar/node_modules/` — sidecar workspace packages installed from `pnpm-lock.yaml`.
- Create/update: Docker volume `edu_ai_postgres_data` — PostgreSQL data files outside the Git worktree.
- Preserve: existing `.env`, `.env.local`, JSON, SQLite, Chroma, course-storage, and upload directories.

### Task 1: Preflight and Local PostgreSQL Configuration

**Files:**
- Create: `deploy/postgres/.env.postgres`
- Verify: `deploy/postgres/compose.yml`
- Preserve: `Edu_AI/.env`
- Preserve: `backend/src/.env`
- Preserve: `openmaic-sidecar/.env.local`

- [x] **Step 1: Verify the clean tracked worktree and required tools**

Run:

```powershell
git status --short --branch
docker --version
docker compose version
python --version
node --version
npm --version
pnpm --version
ffmpeg -version | Select-Object -First 1
ffprobe -version | Select-Object -First 1
```

Expected: the worktree contains only the plan/design documentation changes; Docker and Compose are installed; Python reports 3.12; pnpm reports 10.28.0; FFmpeg and ffprobe are available. Node 24 may be used if the locked dependency installation and build checks pass.

- [x] **Step 2: Generate the ignored PostgreSQL environment file**

Run from the repository root:

```powershell
$postgresEnv = 'deploy/postgres/.env.postgres'
if (-not (Test-Path -LiteralPath $postgresEnv)) {
    Copy-Item -LiteralPath 'deploy/postgres/.env.example' -Destination $postgresEnv
    $passwordBytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($passwordBytes)
    $password = [Convert]::ToHexString($passwordBytes).ToLowerInvariant()
    $content = Get-Content -Raw -LiteralPath $postgresEnv
    $content = $content.Replace('replace_with_a_long_local_password', $password)
    $content = $content.Replace('replace_with_a_url_encoded_local_password', $password)
    Set-Content -LiteralPath $postgresEnv -Value $content -Encoding utf8
}
```

Expected: `deploy/postgres/.env.postgres` exists, remains ignored by Git, and contains matching URL-safe password values without printing them.

- [x] **Step 3: Validate startup and Compose configuration without starting services**

Run:

```powershell
cmd /c backend\src\start_api.bat --check
docker compose --env-file deploy/postgres/.env.postgres -f deploy/postgres/compose.yml config -q
```

Expected: both commands exit `0`; the startup script prints `Startup script check passed.`

### Task 2: Install Host Dependencies

**Files:**
- Create: `backend/src/.venv/`
- Refresh: `Edu_AI/node_modules/`
- Refresh: `openmaic-sidecar/node_modules/`

- [x] **Step 1: Create the backend environment used by the startup script**

Run:

```powershell
python -m venv backend/src/.venv
backend/src/.venv/Scripts/python.exe --version
```

Expected: the second command reports Python 3.12 and `start_api.bat` can discover this environment.

- [x] **Step 2: Install backend, frontend, and Playwright dependencies**

Run with the local proxy only for package downloads:

```powershell
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
& .\scripts\install-all.ps1 -Python '.\backend\src\.venv\Scripts\python.exe' -SkipOptional
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
```

Expected: pip, the backend requirements, `npm ci`, and Playwright Chromium installation all exit `0`; existing local `.env` files are preserved.

- [x] **Step 3: Synchronize OpenMAIC workspace dependencies**

Run:

```powershell
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
pnpm --dir openmaic-sidecar install --frozen-lockfile
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
```

Expected: pnpm exits `0` and does not change `pnpm-lock.yaml`.

- [x] **Step 4: Validate installed dependencies**

Run:

```powershell
backend/src/.venv/Scripts/python.exe -m pip check
npm test --prefix Edu_AI
npm run build --prefix Edu_AI
```

Expected: pip reports no broken requirements; frontend tests and production build exit `0`.

### Task 3: Start and Migrate the Empty PostgreSQL Database

**Files:**
- Use: `deploy/postgres/.env.postgres`
- Use: `deploy/postgres/compose.yml`
- Create/update: Docker volume `edu_ai_postgres_data`

- [x] **Step 1: Start Docker Desktop and prepare the database**

Run:

```powershell
cmd /c backend\src\start_api.bat --database-only
```

Expected: the script starts Docker Desktop if required, starts `edu-ai-postgres`, waits for a healthy state, applies Alembic migrations, and prints `Database-only startup completed successfully.`

- [x] **Step 2: Verify the container, volume, and migration revision**

Run:

```powershell
docker compose --env-file deploy/postgres/.env.postgres -f deploy/postgres/compose.yml ps
docker volume inspect edu_ai_postgres_data --format '{{.Name}}'
$databaseUrlLine = Get-Content -LiteralPath 'deploy/postgres/.env.postgres' | Where-Object { $_ -like 'DATABASE_URL=*' } | Select-Object -First 1
$env:DATABASE_URL = $databaseUrlLine.Substring('DATABASE_URL='.Length)
Push-Location backend/src
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic heads
Pop-Location
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

Expected: Compose reports `edu-ai-postgres` healthy, the named volume exists, and `alembic current` matches the single revision printed by `alembic heads`.

### Task 4: Launch and Verify the Application Stack

**Files:**
- Use: `backend/src/.env`
- Use: `openmaic-sidecar/.env.local`
- Use: `deploy/postgres/.env.postgres`

- [x] **Step 1: Start OpenMAIC, the frontend, and the backend as hidden host processes**

Run from PowerShell:

```powershell
$databaseUrlLine = Get-Content -LiteralPath 'deploy/postgres/.env.postgres' | Where-Object { $_ -like 'DATABASE_URL=*' } | Select-Object -First 1
$env:DATABASE_URL = $databaseUrlLine.Substring('DATABASE_URL='.Length)
$env:VITE_API_BASE_URL = 'http://localhost:8001'
$env:CLASSROOM_VIDEO_FRONTEND_URL = 'http://127.0.0.1:5173'
Start-Process -FilePath 'pnpm.cmd' -ArgumentList 'dev' -WorkingDirectory (Resolve-Path 'openmaic-sidecar') -WindowStyle Hidden
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','0.0.0.0','--port','5173' -WorkingDirectory (Resolve-Path 'Edu_AI') -WindowStyle Hidden
Start-Process -FilePath (Resolve-Path 'backend/src/.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8001' -WorkingDirectory (Resolve-Path 'backend/src') -WindowStyle Hidden
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

Expected: three processes remain running and begin listening on ports 3000, 5173, and 8001.

- [x] **Step 2: Poll service readiness and verify database connectivity**

Run:

```powershell
$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 2
    try { $sidecar = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000/api/health' -TimeoutSec 3 } catch { $sidecar = $null }
    try { $frontend = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 3 } catch { $frontend = $null }
    try { $database = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health/database' -TimeoutSec 3 } catch { $database = $null }
} until (($sidecar.StatusCode -eq 200 -and $frontend.StatusCode -eq 200 -and $database.status -eq 'ready') -or (Get-Date) -ge $deadline)
[PSCustomObject]@{
    SidecarHttp = $sidecar.StatusCode
    FrontendHttp = $frontend.StatusCode
    DatabaseStatus = $database.status
} | Format-List
```

Expected: sidecar and frontend return HTTP `200`; the backend database health payload reports status `ready`.

- [x] **Step 3: Confirm persistence and repository hygiene**

Run:

```powershell
docker inspect --format '{{.State.Health.Status}}' edu-ai-postgres
docker volume inspect edu_ai_postgres_data --format '{{.Mountpoint}}'
git status --short --branch
git check-ignore -v deploy/postgres/.env.postgres backend/src/.venv
```

Expected: PostgreSQL is healthy, the volume has a Docker-managed mount point, local secrets and the virtual environment are ignored, and no unintended tracked files changed.

### Task 5: Record Completion Evidence

**Files:**
- Modify: `docs/superpowers/plans/2026-08-24-local-docker-postgres-bootstrap.md`

- [x] **Step 1: Mark completed checkboxes only after their commands pass**

Update each successful step from `- [ ]` to `- [x]`. Leave any failed step unchecked and record the exact blocker below that step.

- [x] **Step 2: Re-run the final health snapshot**

Run:

```powershell
docker compose --env-file deploy/postgres/.env.postgres -f deploy/postgres/compose.yml ps
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health/database' -TimeoutSec 5
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 5).StatusCode
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000/api/health' -TimeoutSec 5).StatusCode
git status --short --branch
```

Expected: PostgreSQL is healthy, database health is `ready`, both HTTP checks return `200`, and Git shows only the intended documentation update.

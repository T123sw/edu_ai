# Local Docker PostgreSQL Bootstrap Design

Date: 2026-08-24

## Goal

Prepare this Windows development machine to run Edu AI against a new, empty PostgreSQL database stored in Docker. Install the repository's required local dependencies, start the application stack, and verify that the database, API, and frontend are reachable.

The populated PostgreSQL database from the other device will be transferred later. No legacy JSON or SQLite business data will be imported during this bootstrap.

## Scope

Included:

- Create the Python 3.12 virtual environment at `Edu_AI/api/src/.venv`, which is the first environment discovered by the repository startup script.
- Install locked frontend dependencies and required backend dependencies.
- Install the browser/runtime dependencies required by the repository's normal local startup path.
- Create a local, Git-ignored `infra/postgres/.env.postgres` with a generated password.
- Start PostgreSQL 17 from `infra/postgres/compose.yml`.
- Persist the database in the named Docker volume `edu_ai_postgres_data`.
- Apply all Alembic migrations to create the current schema.
- Start the normal local application services.
- Verify database health, backend health, and frontend availability.

Excluded:

- Importing existing JSON, SQLite, Chroma, uploaded-file, or course-storage data.
- Copying the PostgreSQL database from the other device.
- Changing tracked application behavior or committing secrets.
- Deleting any existing local legacy data.

## Architecture and Data Flow

The FastAPI backend runs on the Windows host and connects to PostgreSQL through `127.0.0.1:5432`. Docker Compose exposes the container only on loopback. PostgreSQL stores its files in the named Docker volume rather than in the Git worktree.

`infra/postgres/.env.postgres` is the local source of the database name, user, password, port, and SQLAlchemy `DATABASE_URL`. The existing startup script reads this file, starts PostgreSQL, waits for its health check, injects `DATABASE_URL`, and applies Alembic migrations before starting the backend.

The React frontend connects to the FastAPI backend through the existing `VITE_API_BASE_URL`. OpenMAIC and any other repository-managed runtime required by the normal startup script remain host processes and do not store PostgreSQL data.

## Configuration Safety

- Generate a long random local password and URL-encode it in `DATABASE_URL`.
- Keep `.env.postgres` and application `.env` files untracked.
- Do not print secrets in progress reports or command output.
- Do not use `docker compose down -v`; removing the volume would delete database data.
- Do not modify or delete the existing ignored JSON, SQLite, Chroma, or storage directories.

## Dependency Strategy

Use the repository's installation scripts and lockfiles. Prefer the `Edu_AI/api/src/.venv` Python interpreter for all backend commands. Install the required backend, frontend, and Playwright dependencies; skip only components explicitly marked optional when they are not required by the normal Edu AI startup path.

Before installation, record installed versions of Docker, Docker Compose, Python, Node.js, npm, FFmpeg, and ffprobe. A version mismatch is handled as an environment issue rather than by changing application source code.

## Startup and Failure Handling

1. Ensure Docker Desktop's engine is running.
2. Validate the Compose configuration using the local PostgreSQL environment file.
3. Start PostgreSQL and wait until Docker reports it healthy.
4. Apply Alembic migrations to `head`.
5. Start the repository's normal application stack.
6. Stop and diagnose the first failing boundary if Docker, dependency installation, migration, or service health checks fail.

Commands must be idempotent where practical: existing environment files are preserved, locked dependencies may be reinstalled safely, Compose reuses the named volume, and Alembic reapplies only unapplied migrations.

## Verification

Completion requires fresh evidence for all of the following:

- `docker compose ps` reports `edu-ai-postgres` healthy.
- The Docker volume `edu_ai_postgres_data` exists.
- Alembic reports the database at the repository's current head revision.
- Python dependency validation succeeds.
- The frontend dependency install/build or equivalent repository check succeeds.
- The backend health endpoint confirms database connectivity.
- The frontend responds on its configured local URL.
- `git status` shows no tracked secret or unintended source changes.

## Later Database Transfer

When the populated database arrives from the other device, use a PostgreSQL logical backup and restore flow (`pg_dump`/`pg_restore`) rather than re-importing legacy JSON or SQLite data. Before restoring, stop application writers, preserve or replace the temporary local database intentionally, restore the backup, apply any newer Alembic migrations, and rerun health checks.

Uploaded files, course assets, and vector indexes are outside the PostgreSQL logical backup and must be transferred or rebuilt separately if the restored rows reference them.

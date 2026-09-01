# Repository Cleanup and Layout Migration Plan

> Status: approved and in progress. This plan implements the cleanup decisions confirmed on 2026-09-01. Every phase is an independent Git commit and must leave the repository in a reviewable state.

## Objective

Turn the current mixed historical repository into one deployable `Edu_AI` project with clear frontend, backend, OpenMAIC sidecar, deployment, scripts, and documentation boundaries. Remove retired products instead of carrying compatibility shims into Linux deployment.

## Safety and rollback contract

- Baseline branch: `main` at `95bc7d19e639fcf751a3dabcf8217f61054b5710`.
- Baseline rollback tag: `backup/pre-repository-cleanup-20260901`.
- Working branch: `codex/repository-cleanup`.
- Documentation checkpoint: `d57fbfc` (`docs: consolidate project documentation`).
- Do not merge or rewrite the other active worktree while this cleanup is in progress.
- Create one commit per phase. Use `git revert <commit>` to undo one phase, or recreate a branch from the baseline tag to abandon the whole cleanup.
- Preserve user-uploaded `.ppt`/`.pptx` knowledge inputs and teaching-video source presentations. Do not delete or rewrite production database records during repository cleanup.
- Known backend test failures are recorded baseline debt; report them without expanding this cleanup into unrelated fixes.

## Canonical target layout

```text
Edu_AI/
├── frontend/
├── backend/
├── openmaic-sidecar/
├── deploy/
│   ├── postgres/
│   ├── systemd/
│   └── nginx/
├── scripts/
├── docs/
├── environment.yml
├── README.md
├── AGENTS.md
├── .gitignore
└── 项目总览地图.md
```

Windows working root becomes `D:\Edu_AI`; Linux deployment root becomes `/home/zxqs_ep/Edu_AI`.

## Phase 0 — Documentation checkpoint

Completed in commit `d57fbfc`.

- Consolidated active documentation under root `docs/`.
- Removed historical subsystem-owned documentation and obsolete generated evidence.
- Recorded the confirmed Linux server facts and deployment boundaries.

## Phase 1 — Remove confirmed retired modules

Completed in commit `762e60d`.

### Scope

- Delete unreachable legacy frontend `Edu_AI/src/pages/**`.
- Delete frontend tests that exist only to assert legacy `src/pages` styles or paths.
- Delete backend `Edu_AI/api/src/app/pipeline/**` and unregister `/api/pipeline` from `app/bootstrap.py`.
- Delete the repository-root `automation_spider/**` implementation and its dedicated smoke script.
- Delete the complete repository-root `EduAgent/**` product.
- Delete retired `infra/searxng/**` configuration.
- Remove installer and ignore-file entries that exist only for EduAgent, the crawler, or SearXNG.
- Remove remaining live-code references to these retired modules while preserving historical specifications that explicitly describe their retirement.

### Verification

- `rg` finds no runtime imports or routes for `app.pipeline`, `automation_spider`, `EduAgent`, or SearXNG outside historical documentation.
- Frontend type/build checks do not depend on `src/pages`.
- Backend application import succeeds without the pipeline package.
- Run targeted frontend and backend tests covering bootstrap and current Stitch entry points.

### Commit

`refactor: remove retired frontend and data pipeline modules`

## Phase 2 — Retire generic PPT and HTML2PPT

Completed in commit `5dd4c90`.

### Scope

- Inventory every generic PPT route, workflow, tool contract, prompt, frontend entry, dependency, environment key, and test.
- First move any shared image-extraction/report helper out of `app.chat.workflows.ppt` into a neutral report or media module.
- Remove direct/generic PPT APIs and HTML2PPT calls, including fallback or redirect behavior.
- Remove generic PPT intent recognition and recommendations. Do not reinterpret those requests as AI classroom generation.
- Keep only OpenMAIC presentation export: `src/openmaic/pptxExporter.ts`, its UI export action, required packages, and its tests.
- Delete obsolete generated PPT drafts, logs, and generated materials while preserving user-uploaded knowledge presentations and teaching-video source presentations.

### Verification

- Repository search shows no HTML2PPT endpoint, environment key, client, route, or generic PPT intent handler.
- OpenMAIC PPTX unit/integration tests pass.
- Report generation tests pass after shared helper relocation.
- Frontend build succeeds.

### Commit

`refactor: keep only OpenMAIC presentation export`

## Phase 3 — Remove tracked residue and define runtime-data boundaries

### Scope

- Inspect root `app/`, `models/`, `storage/`, `tests/`, temporary import-test directories, caches, build output, and duplicate configuration.
- Delete only confirmed tracked residue or generated artifacts; do not blindly delete unreachable code.
- Strengthen `.gitignore` for virtual environments, package stores, builds, caches, runtime uploads, model weights, logs, generated presentations, and temporary work directories.
- Document external runtime-data paths for Linux. Do not commit runtime data or model weights.

### Verification

- `git status --ignored` shows generated artifacts are ignored.
- No tracked cache, environment, build, uploaded asset, model weight, or generated-output directory remains.
- Application tests that depend on fixtures still find their intended test data.

### Commit

`chore: remove generated residue and isolate runtime data`

## Phase 4 — Migrate to the canonical root layout

### Scope

- Rename the repository root to `Edu_AI` outside Git only after the internal layout is ready.
- Move current Vite/React application to `frontend/`.
- Move FastAPI application to `backend/`.
- Keep the current OpenMAIC Next.js service at `openmaic-sidecar/`.
- Consolidate PostgreSQL, systemd, and Nginx assets under `deploy/`.
- Consolidate supported operational scripts under `scripts/`.
- Keep documentation and root governance files at the canonical root.
- Update imports, workspace scripts, test paths, static paths, service working directories, and documentation links in the same commit.

### Verification

- No tracked path refers to the former nested `Edu_AI/` layout.
- Frontend build, backend application import, sidecar tests/build, and path-contract tests pass.
- All deployment files resolve only canonical root paths.

### Commit

`refactor: adopt canonical Edu_AI repository layout`

## Phase 5 — Unify environment and Linux deployment

### Supported baseline

- Miniforge/Conda with one root `environment.yml`.
- Python 3.12.
- Node.js 22.
- pnpm 10.28.
- FFmpeg/ffprobe 6 or newer.
- FastAPI on `127.0.0.1:8001`.
- OpenMAIC sidecar on `127.0.0.1:3000`.
- PostgreSQL on `127.0.0.1:5432`.
- Nginx as the public reverse proxy/static frontend entry.

### Scope

- Replace conflicting Python environment definitions with one root `environment.yml` and one locked/derived pip dependency boundary where Conda cannot supply a package.
- Rewrite installation scripts for the supported baseline only.
- Align README, systemd, Nginx, environment examples, health checks, ports, working directories, and storage directories.
- Account for the confirmed server state: Ubuntu 22.04, no Docker, no Node/npm, no Conda, no FFmpeg, Python 3.10 system default, full sudo with password, user systemd available with `Linger=no`, two RTX 3090 GPUs.
- Do not enable lingering, install packages, open firewall ports, or mutate the server in this repository-cleanup phase.

### Verification

- Static consistency scan finds no obsolete root path, port 8000/46080, Python 3.10/3.11 runtime target, npm/yarn install flow, Docker requirement, EduAgent, crawler, SearXNG, HTML2PPT, or generic PPT service in active deployment assets.
- Fresh-environment commands documented in README correspond exactly to checked-in files.
- Service and Nginx configuration syntax checks are documented and runnable on Linux.

### Commit

`deploy: unify Linux environment and service configuration`

## Final acceptance and integration

1. Run frontend tests and production build.
2. Run backend tests and distinguish pre-existing baseline failures from cleanup regressions.
3. Run OpenMAIC tests and production build.
4. Run repository-wide path, documentation-link, secret-pattern, generated-file, and deployment-consistency checks.
5. Record the final verification report under `docs/operations/qa/`.
6. Create a final annotated tag on the accepted cleanup commit.
7. Review the cleanup branch before merging into `main`; do not force-push or rewrite `main`.

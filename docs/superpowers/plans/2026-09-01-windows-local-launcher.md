# Windows Local Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe Windows one-click start/stop entrypoints for the canonical three-service repository, rename the checkout to `D:\Edu_AI`, preserve all linked worktrees, and verify the running stack with Playwright.

**Architecture:** Root BAT files remain thin user-facing wrappers. PowerShell controllers own environment validation, `.env` loading, visible terminal creation, PID manifests, health checks, and safe shutdown. A Python contract suite verifies the launcher source before runtime tests; a focused Playwright test verifies the real three-service stack.

**Tech Stack:** Windows Batch, PowerShell 7/Windows PowerShell 5.1-compatible syntax, Python 3.12 `unittest`, FastAPI/Uvicorn, Node.js 22+, pnpm 10.28, Vite, Next.js, Playwright, Git worktrees.

---

## File map

- Create `start.bat`: stable root entrypoint; maps `--check` and `--no-browser` to PowerShell switches.
- Create `stop.bat`: stable root stop entrypoint.
- Create `scripts/start-dev.ps1`: validates and starts the three services.
- Create `scripts/stop-dev.ps1`: stops only PID-manifest-owned process trees.
- Create `scripts/tests/test_windows_launcher_contract.py`: source and check-mode regression contract.
- Create `frontend/tests/e2e/local-launcher-smoke.spec.ts`: live-stack browser smoke test.
- Modify `.gitignore`: ignore `/.runtime/`.
- Modify `README.md`: document Windows start, check, and stop commands.
- Modify `docs/superpowers/specs/2026-09-01-windows-local-launcher-design.md`: clarify that local Node.js accepts major version 22 or newer while production remains pinned to 22.
- Create `docs/operations/qa/2026-09-01-windows-local-launcher-acceptance.md`: record rename, worktree preservation, runtime, E2E, and stop evidence.

### Task 1: Add the failing launcher contract

**Files:**
- Create: `scripts/tests/test_windows_launcher_contract.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing contract test**

Create a `unittest` suite that reads the intended launcher files from the repository root and asserts:

```python
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WindowsLauncherContractTests(unittest.TestCase):
    def test_required_launchers_exist(self) -> None:
        for relative in (
            "start.bat",
            "stop.bat",
            "scripts/start-dev.ps1",
            "scripts/stop-dev.ps1",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_launcher_uses_canonical_services_and_ports(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
        for token in ("frontend", "backend/src", "openmaic-sidecar", "5173", "8001", "3000"):
            self.assertIn(token, source)
        self.assertNotIn("HTML2PPT", source)
        self.assertNotIn("EduAgent", source)

    def test_startup_never_kills_unknown_port_owners(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8").lower()
        self.assertNotIn("taskkill", source)
        self.assertIn("get-nettcpconnection", source)

    def test_stop_requires_owned_pid_manifest(self) -> None:
        source = (ROOT / "scripts/stop-dev.ps1").read_text(encoding="utf-8")
        self.assertIn("dev-processes.json", source)
        self.assertIn("Win32_Process", source)
        self.assertIn("CommandLine", source)

    def test_runtime_state_is_ignored(self) -> None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".runtime/probe"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest scripts.tests.test_windows_launcher_contract -v`

Expected: FAIL because `start.bat`, `stop.bat`, and the PowerShell controllers do not exist, and `/.runtime/` is not ignored.

- [ ] **Step 3: Add only the runtime ignore rule**

Add this rule under test/tool temporary files:

```gitignore
/.runtime/
```

- [ ] **Step 4: Re-run and preserve the expected launcher failures**

Run: `python -m unittest scripts.tests.test_windows_launcher_contract -v`

Expected: runtime-ignore assertion passes; launcher assertions still fail because production files do not exist.

### Task 2: Implement safe start and stop controllers

**Files:**
- Create: `start.bat`
- Create: `stop.bat`
- Create: `scripts/start-dev.ps1`
- Create: `scripts/stop-dev.ps1`
- Test: `scripts/tests/test_windows_launcher_contract.py`

- [ ] **Step 1: Create thin BAT wrappers**

`start.bat` resolves `%~dp0`, maps the two supported long options, and calls:

```bat
@echo off
setlocal EnableExtensions
set "CHECK_ARG="
set "BROWSER_ARG="
if /I "%~1"=="--check" set "CHECK_ARG=-Check"
if /I "%~1"=="--no-browser" set "BROWSER_ARG=-NoBrowser"
if /I "%~2"=="--no-browser" set "BROWSER_ARG=-NoBrowser"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev.ps1" %CHECK_ARG% %BROWSER_ARG%
exit /b %ERRORLEVEL%
```

`stop.bat` calls `scripts/stop-dev.ps1` and returns its exit code.

- [ ] **Step 2: Implement shared startup validation**

In `start-dev.ps1`, define `[switch]$Check` and `[switch]$NoBrowser`, resolve the root from `$PSScriptRoot`, and validate exact canonical paths. Resolve Python by checking version 3.12 and imports `fastapi`/`uvicorn`. Resolve system Node.js major version 22 or newer, and invoke pnpm through `corepack pnpm`; require pnpm major 10. Validate both `node_modules` directories and root `.env`.

Load `.env` lines matching `^[A-Za-z_][A-Za-z0-9_]*=` into process environment, trimming matching single or double outer quotes without printing values. Override only the frontend child environment with `VITE_API_BASE_URL=http://127.0.0.1:8001`.

- [ ] **Step 3: Implement strict port ownership checks**

Use `Get-NetTCPConnection -State Listen -LocalPort <port> -ErrorAction SilentlyContinue`. If any of 3000, 8001, or 5173 is occupied, print the port and owning PID and exit nonzero. Do not call `Stop-Process` or `taskkill` in `start-dev.ps1`.

- [ ] **Step 4: Implement visible terminals, manifest, and health waits**

Create `.runtime/`, generate one command file per service, and launch each through `Start-Process cmd.exe -ArgumentList '/d','/k',<command-file> -PassThru`. Command files use `cd /d` and these commands:

```text
corepack pnpm dev -- --hostname 127.0.0.1 --port 3000
<python> -m uvicorn app.main:app --host 127.0.0.1 --port 8001
corepack pnpm dev -- --host 127.0.0.1 --port 5173
```

After each process starts, write `.runtime/dev-processes.json` with repository root, UTC start time, service name, PID, port, and command-file path. Poll `/api/health`, `/health`, and `/` for at most 120 seconds. On failure, call `stop-dev.ps1`; on success, open the frontend unless `-NoBrowser` is set.

- [ ] **Step 5: Implement manifest-owned shutdown**

In `stop-dev.ps1`, return success when the manifest is absent. For every manifest entry, load `Win32_Process` by PID and require its `CommandLine` to contain the recorded command-file path before running:

```powershell
& taskkill.exe /PID $entry.pid /T /F
```

Skip mismatched/reused PIDs, remove generated command files, then remove the manifest.

- [ ] **Step 6: Run contract and parser checks**

Run:

```powershell
python -m unittest scripts.tests.test_windows_launcher_contract -v
$tokens = $null; $errors = $null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'scripts/start-dev.ps1'), [ref]$tokens, [ref]$errors) | Out-Null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'scripts/stop-dev.ps1'), [ref]$tokens, [ref]$errors) | Out-Null
```

Expected: all contract tests pass and both parser error counts are zero.

- [ ] **Step 7: Commit the launcher**

Run:

```text
git add .gitignore start.bat stop.bat scripts/start-dev.ps1 scripts/stop-dev.ps1 scripts/tests/test_windows_launcher_contract.py
git commit -m "feat: add safe Windows local launcher"
```

### Task 3: Document and smoke-test the launcher contract

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-01-windows-local-launcher-design.md`
- Create: `frontend/tests/e2e/local-launcher-smoke.spec.ts`

- [ ] **Step 1: Add the failing live-stack Playwright test**

Create a test that opens `/`, checks `#root` is visible and non-empty, fetches `http://127.0.0.1:8001/health` from the browser page, and requests `http://127.0.0.1:3000/api/health` through Playwright. Require 2xx responses.

```ts
import { expect, test } from "playwright/test";

test("local launcher exposes frontend, backend, and OpenMAIC", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.locator("#root")).toBeVisible();
  await expect(page.locator("#root")).not.toBeEmpty();

  const backendStatus = await page.evaluate(async () => {
    const response = await fetch("http://127.0.0.1:8001/health");
    return response.status;
  });
  expect(backendStatus).toBeGreaterThanOrEqual(200);
  expect(backendStatus).toBeLessThan(300);

  const openmaic = await request.get("http://127.0.0.1:3000/api/health");
  expect(openmaic.ok()).toBeTruthy();
});
```

- [ ] **Step 2: Clarify the local runtime baseline**

Update the design to say local Windows accepts Node.js 22 or newer because the verified host has Node.js 24, while `environment.yml` and Linux production remain pinned to 22.

- [ ] **Step 3: Document Windows commands**

Add to `README.md`:

```text
start.bat --check
start.bat
stop.bat
```

Explain the three windows, ports, `.env` prerequisite, strict occupied-port behavior, and that startup never installs dependencies.

- [ ] **Step 4: Run source tests and commit**

Run `python -m unittest scripts.tests.test_windows_launcher_contract -v`, then commit the test and documentation as `test: add Windows launcher smoke coverage`.

### Task 4: Rename the checkout and repair every worktree

**Files:**
- Move filesystem root: `D:\Edu_AI_1` to `D:\Edu_AI`
- Preserve: `D:\Edu_AI\.worktrees\**`

- [ ] **Step 1: Commit and record pre-move evidence**

Require the main worktree to be clean. Record every worktree path, branch, HEAD, and porcelain status count. Confirm `D:\Edu_AI` does not exist and ports 3000, 5173, 8001 are free.

- [ ] **Step 2: Move the exact verified directory**

From working directory `D:\`, resolve `D:\Edu_AI_1`, verify it is the expected source and target is absent, then use PowerShell `Move-Item -LiteralPath 'D:\Edu_AI_1' -Destination 'D:\Edu_AI'`. Do not copy/delete or recreate worktrees.

- [ ] **Step 3: Repair Git worktree metadata**

From `D:\Edu_AI`, enumerate the moved `.worktrees` directories and run `git worktree repair` with every new absolute path. Verify `git worktree list --porcelain` contains no `D:/Edu_AI_1` path.

- [ ] **Step 4: Verify preservation**

For the main worktree and every linked worktree, compare branch, HEAD, and status count to the pre-move record. Any mismatch stops the task before runtime startup.

### Task 5: Run the real stack and end-to-end smoke test

**Files:**
- Runtime only: `.env`, `.runtime/`
- Create: `docs/operations/qa/2026-09-01-windows-local-launcher-acceptance.md`

- [ ] **Step 1: Prepare non-secret local configuration**

If root `.env` is absent, copy `.env.example` to `.env` as an ignored runtime file. Do not insert keys or commit the file.

- [ ] **Step 2: Run check mode**

Run `cmd.exe /d /c start.bat --check --no-browser` from `D:\Edu_AI`.

Expected: exit 0 with Python, Node, pnpm, dependency, path, `.env`, and port checks passing.

- [ ] **Step 3: Start all services**

Run `cmd.exe /d /c start.bat --no-browser`.

Expected: three visible terminals, three health checks pass, and `.runtime/dev-processes.json` contains exactly three owned processes.

- [ ] **Step 4: Execute live HTTP and Playwright checks**

Run direct HTTP checks for frontend `/`, backend `/health`, OpenMAIC `/api/health`, then:

```text
cd frontend
corepack pnpm exec playwright test tests/e2e/local-launcher-smoke.spec.ts --project=desktop1366
```

Expected: one Playwright test passes without real model calls.

- [ ] **Step 5: Stop and verify cleanup**

Run `cmd.exe /d /c stop.bat`. Confirm 3000, 5173, 8001 are no longer listening, the manifest is absent, and the three generated command files are removed.

- [ ] **Step 6: Record QA and commit**

Record exact versions, endpoints, test results, rename evidence, and worktree preservation in the QA document. Run `git diff --check`, commit as `docs: record Windows launcher acceptance`, and create annotated tag `launcher/windows-local-accepted-20260901`.

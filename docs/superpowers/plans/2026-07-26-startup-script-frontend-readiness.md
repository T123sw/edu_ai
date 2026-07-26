# Startup Script Frontend Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the unified Windows startup script repair an incomplete frontend dependency installation and refuse to start the backend until Vite is reachable.

**Architecture:** Keep startup orchestration in the existing batch file. Replace the directory-only frontend dependency probe with a Vite launcher probe, then add a PowerShell HTTP health function and bounded polling loop that mirrors the existing OpenMAIC readiness pattern.

**Tech Stack:** Windows batch, PowerShell `Invoke-WebRequest`, pytest source-contract tests, npm/Vite

---

## File Structure

- Modify `Edu_AI/api/src/start_api.bat`: validate the Vite launcher, repair missing frontend dependencies, wait for the frontend HTTP service, and stop before backend startup on failure.
- Modify `Edu_AI/api/src/tests/chat/test_start_api_bat.py`: enforce the dependency probe, post-install validation, frontend wait call, ordering, and nonzero failure path.

### Task 1: Lock the Broken Startup Behaviors with Tests

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/test_start_api_bat.py`
- Test: `Edu_AI/api/src/tests/chat/test_start_api_bat.py`

- [ ] **Step 1: Add the failing dependency-probe tests**

Append:

```python
def test_start_api_bat_checks_the_vite_launcher_not_only_node_modules():
    script = _read(API_ROOT / "start_api.bat")

    assert 'set "frontend_vite_cmd=%frontend_dir%\\node_modules\\.bin\\vite.cmd"' in script
    assert 'if not exist "%frontend_vite_cmd%" (' in script
    assert 'if not exist "%frontend_dir%\\node_modules" (' not in script


def test_start_api_bat_verifies_vite_after_frontend_install():
    script = _read(API_ROOT / "start_api.bat")

    install_index = script.index("call npm.cmd install")
    verify_index = script.index(
        'if not exist "%frontend_vite_cmd%" (',
        install_index,
    )
    assert install_index < verify_index
    assert "vite launcher is still missing" in script
```

- [ ] **Step 2: Add the failing frontend-readiness tests**

Append:

```python
def test_start_api_bat_waits_for_frontend_before_backend():
    script = _read(API_ROOT / "start_api.bat")

    start_index = script.index('start "edu-ai-frontend"')
    wait_index = script.index("call :wait_for_frontend", start_index)
    backend_index = script.rindex("-m uvicorn")

    assert start_index < wait_index < backend_index
    assert ":frontend_health" in script
    assert "http://127.0.0.1:%frontend_port%/" in script


def test_start_api_bat_stops_when_frontend_never_becomes_ready():
    script = _read(API_ROOT / "start_api.bat")

    wait_index = script.index("call :wait_for_frontend")
    failure_index = script.index(
        "frontend did not become ready within 90 seconds",
        wait_index,
    )
    backend_index = script.rindex("-m uvicorn")
    failure_block = script[failure_index:backend_index]

    assert "exit /b 1" in failure_block
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest Edu_AI/api/src/tests/chat/test_start_api_bat.py -q
```

Expected: four new tests fail because the script still checks only `node_modules` and has no frontend readiness function.

- [ ] **Step 4: Commit the RED tests**

```powershell
git add -- Edu_AI/api/src/tests/chat/test_start_api_bat.py
git commit -m "test(startup): require frontend readiness checks"
```

### Task 2: Repair Dependencies and Gate Backend Startup

**Files:**
- Modify: `Edu_AI/api/src/start_api.bat`
- Test: `Edu_AI/api/src/tests/chat/test_start_api_bat.py`

- [ ] **Step 1: Replace the frontend directory probe with a launcher probe**

Immediately after the port variables, add:

```bat
set "FRONTEND_VITE_CMD=%FRONTEND_DIR%\node_modules\.bin\vite.cmd"
```

Replace the `if not exist "%FRONTEND_DIR%\node_modules"` block with:

```bat
if not exist "%FRONTEND_VITE_CMD%" (
    echo Frontend Vite launcher not found. Running npm install...
    pushd "%FRONTEND_DIR%"
    call npm.cmd install
    set "NPM_RESULT=!ERRORLEVEL!"
    popd
    if !NPM_RESULT! NEQ 0 (
        echo [ERROR] Frontend npm install failed.
        pause
        exit /b 1
    )
    if not exist "%FRONTEND_VITE_CMD%" (
        echo [ERROR] Frontend Vite launcher is still missing after npm install.
        pause
        exit /b 1
    )
) else (
    echo Frontend Vite launcher found.
)
```

- [ ] **Step 2: Wait for Vite immediately after starting it**

After the frontend `start` command, add:

```bat
call :wait_for_frontend
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Frontend did not become ready within 90 seconds.
    echo Check the "edu-ai-frontend" terminal for the startup error.
    pause
    exit /b 1
)
echo Frontend is ready at http://localhost:%FRONTEND_PORT%.
```

- [ ] **Step 3: Add the bounded frontend HTTP polling functions**

Place these labels beside the existing sidecar health functions:

```bat
:frontend_health
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
    "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%FRONTEND_PORT%/' -TimeoutSec 2; if ($response.StatusCode -lt 500) { exit 0 } } catch {}; exit 1" ^
    >nul 2>nul
exit /b %ERRORLEVEL%

:wait_for_frontend
set "FRONTEND_HEALTH_ATTEMPTS=0"

:wait_for_frontend_loop
call :frontend_health
if !ERRORLEVEL! EQU 0 exit /b 0
set /a FRONTEND_HEALTH_ATTEMPTS+=1
if !FRONTEND_HEALTH_ATTEMPTS! GEQ 45 exit /b 1
timeout /t 2 /nobreak >nul
goto :wait_for_frontend_loop
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest Edu_AI/api/src/tests/chat/test_start_api_bat.py -q
```

Expected: 14 tests pass.

- [ ] **Step 5: Run the batch structural check**

Run:

```powershell
cmd.exe /d /c Edu_AI\api\src\start_api.bat --check
```

Expected: `Startup script check passed.` and exit code 0.

- [ ] **Step 6: Commit the implementation**

```powershell
git add -- Edu_AI/api/src/start_api.bat
git commit -m "fix(startup): wait for frontend readiness"
```

### Task 3: Repair and Validate the Current Frontend Installation

**Files:**
- Runtime repair only: `Edu_AI/node_modules`
- Preserve: `Edu_AI/package.json`
- Preserve: `Edu_AI/package-lock.json`

- [ ] **Step 1: Record the user-owned Git state**

Run in the main checkout:

```powershell
git status --short
git diff -- Edu_AI/package.json
```

Expected: only the pre-existing `Edu_AI/package.json` edit is present.

- [ ] **Step 2: Recreate npm command launchers without changing the lockfile**

Run:

```powershell
npm.cmd install --no-package-lock --ignore-scripts --prefer-offline
```

Expected: exit code 0 and `Edu_AI/node_modules/.bin/vite.cmd` exists.

- [ ] **Step 3: Start Vite on an isolated acceptance port**

Run Vite on port 5174 without touching ports 5173, 8001, or 3000:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```

Expected: `http://127.0.0.1:5174/` returns an HTTP response. Stop only the process that owns port 5174 after the check.

- [ ] **Step 4: Confirm the runtime repair did not alter tracked files**

Run:

```powershell
git status --short
git diff -- Edu_AI/package-lock.json
```

Expected: `package-lock.json` has no diff and the user-owned `package.json` edit remains.

### Task 4: Full Verification and Integration

**Files:**
- Verify: `Edu_AI/api/src/start_api.bat`
- Verify: `Edu_AI/api/src/tests/chat/test_start_api_bat.py`

- [ ] **Step 1: Run startup and video backend regression tests**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest Edu_AI/api/src/tests/chat/test_start_api_bat.py Edu_AI/api/src/tests/test_classroom_video_export.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend unit tests**

Run from `Edu_AI`:

```powershell
npm.cmd test
```

Expected: all tests pass.

- [ ] **Step 3: Check patch cleanliness**

Run:

```powershell
git diff --check
git status --short
git log --oneline -4
```

Expected: worktree clean; test and implementation commits appear after the plan commit.

- [ ] **Step 4: Fast-forward merge to main**

Run:

```powershell
git -C D:\github\edu_ai merge --ff-only fix/startup-frontend-readiness
```

Expected: `main` advances without including the user-owned `Edu_AI/package.json` edit.

- [ ] **Step 5: Re-run focused tests on main**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest Edu_AI/api/src/tests/chat/test_start_api_bat.py Edu_AI/api/src/tests/test_classroom_video_export.py -q
```

Expected: all selected tests pass on `main`.

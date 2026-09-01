from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_start_api_bat_does_not_start_retired_sidecars():
    script = _read(API_ROOT / "start_api.bat")

    for retired_marker in (
        "html2ppt",
        "ai_lecturer",
        "ppt_dir",
        "ppt_port",
        "vite_ppt_base_url",
    ):
        assert retired_marker not in script


def test_installers_do_not_install_retired_vendor_dependencies():
    scripts = "\n".join(
        _read(REPO_ROOT / "scripts" / name)
        for name in ("install-all.ps1", "install-all.sh")
    )

    assert "html2ppt" not in scripts
    assert "ai_lecturer" not in scripts


def test_backend_env_example_has_no_retired_service_switches():
    env_example = _read(API_ROOT / ".env.example")

    assert "html2ppt" not in env_example
    assert "ai_lecturer" not in env_example


def test_start_api_bat_checks_fallback_local_venv():
    script = _read(API_ROOT / "start_api.bat")

    assert ".venv_local\\scripts\\python.exe" in script


def test_start_api_bat_validates_pip_before_selecting_venv():
    script = _read(API_ROOT / "start_api.bat")

    assert "import pip" in script


def test_start_api_bat_declares_repository_openmaic_sidecar():
    script = _read(API_ROOT / "start_api.bat")

    assert "openmaic-sidecar" in script
    assert 'set "sidecar_port=3000"' in script
    assert "pnpm.cmd dev" in script


def test_start_api_bat_waits_for_openmaic_health_before_backend():
    script = _read(API_ROOT / "start_api.bat")

    assert "/api/health" in script
    assert "call :wait_for_sidecar" in script
    assert script.index("call :wait_for_sidecar") < script.rindex("-m uvicorn")


def test_start_api_bat_does_not_kill_unknown_sidecar_port_owner():
    script = _read(API_ROOT / "start_api.bat")

    assert 'call :ensure_port_free "%sidecar_port%"' not in script
    assert "sidecar port" in script


def test_start_api_bat_routes_video_export_to_frontend_port():
    script = _read(API_ROOT / "start_api.bat")

    assert 'set "frontend_port=5173"' in script
    assert (
        'set "classroom_video_frontend_url=http://127.0.0.1:%frontend_port%"'
        in script
    )


def test_backend_env_example_matches_unified_video_frontend_port():
    env_example = _read(API_ROOT / ".env.example")

    assert "classroom_video_frontend_url=http://127.0.0.1:5173" in env_example


def test_start_api_bat_checks_the_vite_launcher_not_only_node_modules():
    script = _read(API_ROOT / "start_api.bat")

    assert (
        'set "frontend_vite_cmd=%frontend_dir%\\node_modules\\.bin\\vite.cmd"'
        in script
    )
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

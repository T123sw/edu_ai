from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[5]


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

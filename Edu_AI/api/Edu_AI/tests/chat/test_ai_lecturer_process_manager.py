import importlib.util
from pathlib import Path

from app.teaching_video_bridge import AiLecturerProcessManager
from core import Config


class FakeResponse:
    def __init__(self, ok: bool = True):
        self.ok = ok

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("service unavailable")


class FakeHttpClient:
    checks: list[str] = []
    failures: set[str] = set()

    def __init__(self, *, base_url: str, timeout: float, trust_env: bool):
        self.base_url = str(base_url).rstrip("/")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, path: str):
        target = f"{self.base_url}{path}"
        self.checks.append(target)
        if self.base_url in self.failures:
            raise RuntimeError("connection refused")
        return FakeResponse()


def test_ai_lecturer_health_requires_gateway_and_livetalking(monkeypatch):
    FakeHttpClient.checks = []
    FakeHttpClient.failures = {"http://live"}
    monkeypatch.setattr("app.teaching_video_bridge.httpx.Client", FakeHttpClient)

    manager = AiLecturerProcessManager(
        gateway_url="http://gateway",
        livetalking_url="http://live",
        autostart=False,
    )

    assert manager.is_healthy() is False
    assert "http://gateway/openapi.json" in FakeHttpClient.checks
    assert "http://live/webrtcapi.html" in FakeHttpClient.checks


def test_default_ai_lecturer_entrypoint_starts_unified_stack():
    assert Path(Config.AI_LECTURER_ENTRYPOINT).name == "start_unified.py"


def test_unified_startup_does_not_require_hardcoded_conda_environment():
    startup_script = Path(Config.AI_LECTURER_ENTRYPOINT).read_text(encoding="utf-8")

    assert "AI_LECTURER_CONDA_ENV" in startup_script
    assert "conda activate nerfstream" not in startup_script


def test_unified_startup_loads_backend_env_file():
    startup_script = Path(Config.AI_LECTURER_ENTRYPOINT).read_text(encoding="utf-8")

    assert "load_dotenv" in startup_script
    assert 'BASE_DIR, "..", ".env"' in startup_script


def test_unified_startup_can_read_env_without_python_dotenv():
    startup_script = Path(Config.AI_LECTURER_ENTRYPOINT).read_text(encoding="utf-8")

    assert "def _load_env_file" in startup_script
    assert 'line.partition("=")' in startup_script
    assert "_load_env_file(BACKEND_ENV_PATH)" in startup_script


def test_config_defines_base_dir_without_python_dotenv():
    config_source = Path("core/config.py").read_text(encoding="utf-8")

    assert config_source.index("BASE_DIR = Path(__file__).resolve().parents[1]") < config_source.index("try:")


def _load_start_unified_module():
    module_path = Path(Config.AI_LECTURER_ENTRYPOINT)
    spec = importlib.util.spec_from_file_location("start_unified_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_start_named_window_wraps_compound_command_for_cmd(monkeypatch):
    module = _load_start_unified_module()
    recorded = {}

    def fake_popen(command, shell):
        recorded["command"] = command
        recorded["shell"] = shell
        return object()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    module._start_named_window("LiveTalking WebRTC (8010)", 'cd /d "D:\\demo" && python app.py')

    assert recorded["shell"] is True
    assert 'cmd /k "cd /d ""D:\\demo"" && python app.py"' in recorded["command"]

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

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.speech.routes import router as speech_router


def test_speech_transcribe_route_returns_transcript(monkeypatch):
    app = FastAPI()
    app.include_router(speech_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyTranscriber:
        def transcribe(self, input_path, *, dev_pid=1537):
            assert input_path.exists()
            assert input_path.suffix == ".mp3"
            assert dev_pid == 1537
            return "测试转写结果"

    monkeypatch.setattr("app.speech.routes._get_transcriber", lambda: DummyTranscriber())

    client = TestClient(app)
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("sample.mp3", b"fake-audio", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "sample.mp3",
        "text": "测试转写结果",
    }


def test_speech_transcribe_route_rejects_unsupported_file_type():
    app = FastAPI()
    app.include_router(speech_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    client = TestClient(app)
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("sample.txt", b"not-audio", "text/plain")},
    )

    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]

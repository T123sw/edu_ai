from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.speech.routes import router as speech_router


def test_speech_transcribe_route_reports_service_unavailable(monkeypatch):
    app = FastAPI()
    app.include_router(speech_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    def raise_unavailable():
        from app.speech.transcribe import SpeechRecognitionError

        raise SpeechRecognitionError("Missing Baidu speech credentials.")

    monkeypatch.setattr("app.speech.routes._get_transcriber", raise_unavailable)

    client = TestClient(app)
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Missing Baidu speech credentials."

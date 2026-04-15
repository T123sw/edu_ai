from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


class SpeechRecognitionError(RuntimeError):
    """Raised when speech transcription fails."""


@dataclass(frozen=True)
class BaiduSpeechConfig:
    app_id: str
    api_key: str
    secret_key: str
    sample_rate: int = 16000
    dev_pid: int = 1537

    @classmethod
    def from_env(cls) -> "BaiduSpeechConfig":
        app_id = os.getenv("BAIDU_SPEECH_APP_ID", "").strip()
        api_key = os.getenv("BAIDU_SPEECH_API_KEY", "").strip()
        secret_key = os.getenv("BAIDU_SPEECH_SECRET_KEY", "").strip()
        sample_rate = int(os.getenv("BAIDU_SPEECH_SAMPLE_RATE", "16000"))
        dev_pid = int(os.getenv("BAIDU_SPEECH_DEV_PID", "1537"))

        if not app_id or not api_key or not secret_key:
            raise SpeechRecognitionError(
                "Missing Baidu speech credentials. "
                "Set BAIDU_SPEECH_APP_ID, BAIDU_SPEECH_API_KEY, and BAIDU_SPEECH_SECRET_KEY."
            )

        return cls(
            app_id=app_id,
            api_key=api_key,
            secret_key=secret_key,
            sample_rate=sample_rate,
            dev_pid=dev_pid,
        )


class BaiduSpeechTranscriber:
    def __init__(self, config: BaiduSpeechConfig):
        self._config = config
        self._client = None

    def transcribe(self, input_path: str | Path, *, dev_pid: int | None = None) -> str:
        source_path = Path(input_path)
        if not source_path.exists() or not source_path.is_file():
            raise SpeechRecognitionError(f"Audio file not found: {source_path}")

        with TemporaryDirectory(prefix="speech_", dir=source_path.parent) as temp_dir:
            wav_path = Path(temp_dir) / f"{source_path.stem}.wav"
            self._convert_to_wav(source_path, wav_path)
            audio = wav_path.read_bytes()

        result = self._client_instance.asr(
            audio,
            "wav",
            self._config.sample_rate,
            {"dev_pid": dev_pid or self._config.dev_pid},
        )

        if result.get("err_no") != 0:
            raise SpeechRecognitionError(result.get("err_msg") or str(result))

        candidates = result.get("result") or []
        text = candidates[0].strip() if candidates else ""
        if not text:
            raise SpeechRecognitionError("Baidu speech API returned an empty transcription result.")

        return text

    @property
    def _client_instance(self):
        if self._client is None:
            try:
                from aip import AipSpeech
            except ImportError as exc:  # pragma: no cover - depends on optional runtime package
                raise SpeechRecognitionError(
                    "Missing dependency 'baidu-aip'. Install it before using speech transcription."
                ) from exc

            self._client = AipSpeech(
                self._config.app_id,
                self._config.api_key,
                self._config.secret_key,
            )
        return self._client

    def _convert_to_wav(self, input_path: Path, output_path: Path) -> None:
        try:
            import ffmpeg
        except ImportError as exc:  # pragma: no cover - depends on optional runtime package
            raise SpeechRecognitionError(
                "Missing dependency 'ffmpeg-python'. Install it before using speech transcription."
            ) from exc

        try:
            (
                ffmpeg.input(str(input_path))
                .output(str(output_path), ar=self._config.sample_rate, ac=1)
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            raise SpeechRecognitionError(f"Audio conversion failed: {exc}") from exc


def build_default_transcriber() -> BaiduSpeechTranscriber:
    return BaiduSpeechTranscriber(BaiduSpeechConfig.from_env())

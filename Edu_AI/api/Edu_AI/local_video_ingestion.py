"""Local video ingestion pipeline for ChromaDB.

Workflow:
1) Sliding-window local slicing (30s window / 20s stride by default)
2) Dual-track extraction:
   - Audio ASR text (faster-whisper / openai-whisper)
   - Text embedding via OpenAI-compatible /v1/embeddings gateway
3) ChromaDB upsert with precise trace metadata
4) Keep local chunks for source trace/playback
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

import chromadb
import ffmpeg
import requests
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings
from tqdm import tqdm


@dataclass(frozen=True)
class VideoChunk:
    """Represents one chunk in original video timeline."""

    chunk_path: Path
    start_time: float
    end_time: float


class LocalVideoRAGIngester:
    """Ingest local long videos into ChromaDB with strict local-file policy."""

    def __init__(
        self,
        *,
        embedding_api_base: str,
        embedding_api_key: str,
        embedding_model: str,
        embedding_backend: str = "openai",
        chroma_persist_dir: Path | str = Path("./storage/vector_db"),
        collection_name: str = "course_videos",
        temp_dir: Path | str = Path("./temp_video_chunks"),
        window_seconds: int = 30,
        stride_seconds: int = 20,
        asr_backend: str = "faster-whisper",
        whisper_model: str = "small",
        embedding_timeout_sec: int = 120,
        embedding_max_retries: int = 3,
        gemini_dimensions: int = 0,
    ) -> None:
        self.embedding_api_base = (embedding_api_base or "").rstrip("/")
        if self.embedding_api_base and not self.embedding_api_base.endswith("/v1"):
            self.embedding_api_base = f"{self.embedding_api_base}/v1"

        self.embedding_api_key = embedding_api_key
        self.embedding_model = embedding_model
        self.embedding_backend = (embedding_backend or "openai").lower()
        self.embedding_timeout_sec = embedding_timeout_sec
        self.embedding_max_retries = embedding_max_retries
        self.gemini_dimensions = gemini_dimensions

        self.window_seconds = window_seconds
        self.stride_seconds = stride_seconds
        self.asr_backend = asr_backend
        self.whisper_model = whisper_model

        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(Path(chroma_persist_dir)),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection: Collection = self.client.get_or_create_collection(name=collection_name)

        self._whisper_model_obj: Optional[Any] = None

    def ingest(self, video_path: str | Path, course_id: str) -> dict[str, Any]:
        """Main entry: slice -> extract -> embed -> store (keep chunks)."""
        src = Path(video_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"Video not found: {src}")

        logging.info("Start ingest: %s", src)
        duration = self._probe_duration_seconds(src)
        chunks = list(self._slice_video(src, duration))

        success = 0
        failed = 0

        for chunk in tqdm(chunks, desc="Ingesting video chunks", unit="chunk"):
            try:
                transcript = self._extract_asr_text(chunk.chunk_path)
                vector = self._embed_chunk_text(transcript)

                self._upsert_chunk(
                    embedding=vector,
                    transcript=transcript,
                    course_id=course_id,
                    source_original_path=str(src),
                    source_chunk_path=str(chunk.chunk_path.resolve()),
                    start_time=chunk.start_time,
                    end_time=chunk.end_time,
                )
                success += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logging.error(
                    "Chunk failed and skipped: %s [%.2f-%.2f], error=%s",
                    chunk.chunk_path,
                    chunk.start_time,
                    chunk.end_time,
                    exc,
                )
                continue

        return {
            "video_path": str(src),
            "course_id": course_id,
            "duration_seconds": duration,
            "total_chunks": len(chunks),
            "success_chunks": success,
            "failed_chunks": failed,
            "collection": self.collection.name,
        }

    def _ensure_ffmpeg_available(self) -> None:
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "未检测到 ffmpeg/ffprobe 可执行文件。请先安装 FFmpeg 并将其加入系统 PATH。"
            ) from exc

    def _probe_duration_seconds(self, video_path: Path) -> float:
        self._ensure_ffmpeg_available()
        info = ffmpeg.probe(str(video_path))
        return float(info["format"]["duration"])

    def _slice_video(self, video_path: Path, duration: float) -> Iterable[VideoChunk]:
        """Sliding window slicing: window=30s, stride=20s (default)."""
        start = 0.0
        idx = 0

        while start < duration:
            end = min(start + self.window_seconds, duration)
            chunk_name = f"chunk_{idx:06d}_{int(start)}_{int(end)}.mp4"
            chunk_path = self.temp_dir / chunk_name

            try:
                (
                    ffmpeg
                    .input(str(video_path), ss=start, t=(end - start))
                    .output(
                        str(chunk_path),
                        vcodec="libx264",
                        acodec="aac",
                        movflags="+faststart",
                        loglevel="error",
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except FileNotFoundError as exc:
                raise RuntimeError("切片失败：系统找不到 ffmpeg 可执行文件，请安装并配置 PATH") from exc

            yield VideoChunk(chunk_path=chunk_path, start_time=start, end_time=end)

            idx += 1
            start += self.stride_seconds

    def _extract_asr_text(self, chunk_path: Path) -> str:
        """Extract subtitle text from chunk audio. Empty string on silent/failure."""
        try:
            if self.asr_backend == "faster-whisper":
                from faster_whisper import WhisperModel  # type: ignore

                if self._whisper_model_obj is None:
                    self._whisper_model_obj = WhisperModel(self.whisper_model)

                segments, _ = self._whisper_model_obj.transcribe(str(chunk_path), vad_filter=True)
                text = " ".join((seg.text or "").strip() for seg in segments).strip()
                return text

            # fallback: openai-whisper
            import whisper  # type: ignore

            if self._whisper_model_obj is None:
                self._whisper_model_obj = whisper.load_model(self.whisper_model)
            result = self._whisper_model_obj.transcribe(str(chunk_path))
            return (result.get("text") or "").strip()

        except Exception as exc:  # noqa: BLE001
            logging.warning("ASR failed on %s: %s", chunk_path, exc)
            return ""

    def _embed_text_via_gateway(self, text: str) -> List[float]:
        """Call OpenAI-compatible /v1/embeddings via configured gateway."""
        if not self.embedding_api_base:
            raise RuntimeError("EMBEDDING_API_BASE 未配置")

        payload: dict[str, Any] = {
            "model": self.embedding_model,
            "input": [text],
        }
        if self.embedding_backend == "gemini" and self.gemini_dimensions > 0:
            payload["dimensions"] = self.gemini_dimensions

        headers = {"Content-Type": "application/json"}
        if self.embedding_api_key:
            headers["Authorization"] = f"Bearer {self.embedding_api_key}"

        url = f"{self.embedding_api_base}/embeddings"

        last_err: Optional[str] = None
        for attempt in range(self.embedding_max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.embedding_timeout_sec)
                if resp.status_code == 200:
                    data = resp.json() or {}
                    items = data.get("data") or []
                    if not items:
                        raise RuntimeError("embedding 响应为空")
                    emb = items[0].get("embedding") if isinstance(items[0], dict) else None
                    if not isinstance(emb, list) or not emb:
                        raise RuntimeError("embedding 向量为空")
                    return [float(x) for x in emb]

                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.embedding_max_retries:
                    time.sleep(min(8, 0.5 * (2 ** attempt)))
                    continue
                raise RuntimeError(f"Embedding API错误: {resp.status_code} - {resp.text}")
            except requests.RequestException as exc:
                last_err = str(exc)
                if attempt < self.embedding_max_retries:
                    time.sleep(min(8, 0.5 * (2 ** attempt)))
                    continue
                raise RuntimeError(f"Embedding 网络请求失败: {last_err}") from exc

        raise RuntimeError(f"Embedding 调用失败: {last_err or 'unknown error'}")

    def _embed_chunk_text(self, transcript: str) -> List[float]:
        payload = (transcript or "").strip() or "[EMPTY_CHUNK]"
        return self._embed_text_via_gateway(payload)

    def _post_text_query_embedding(self, text: str) -> List[float]:
        """Embed query text for retrieval against video vectors."""
        payload = (text or "").strip() or "[EMPTY_QUERY]"
        return self._embed_text_via_gateway(payload)

    def _upsert_chunk(
        self,
        *,
        embedding: List[float],
        transcript: str,
        course_id: str,
        source_original_path: str,
        source_chunk_path: str,
        start_time: float,
        end_time: float,
    ) -> None:
        chunk_id = f"vid_{course_id}_{int(start_time)}_{int(end_time)}_{uuid.uuid4().hex[:8]}"

        self.collection.add(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[transcript],
            metadatas=[
                {
                    "course_id": course_id,
                    "modality": "video",
                    "source_original_path": source_original_path,
                    "source_chunk_path": source_chunk_path,
                    "start_time": float(start_time),
                    "end_time": float(end_time),
                }
            ],
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local video ingestion into ChromaDB")
    parser.add_argument("--video_path", required=True, help="Absolute/local path to .mp4")
    parser.add_argument("--course_id", required=True, help="Course identifier")
    parser.add_argument("--embedding_api_base", required=True, help="OpenAI-compatible embedding API base URL")
    parser.add_argument("--embedding_api_key", required=True, help="Embedding API key")
    parser.add_argument("--embedding_model", default="gemini-embedding-2-preview")
    parser.add_argument("--embedding_backend", default="openai", choices=["openai", "gemini"])
    parser.add_argument("--window_seconds", type=int, default=30)
    parser.add_argument("--stride_seconds", type=int, default=20)
    parser.add_argument("--temp_dir", default="./temp_video_chunks")
    parser.add_argument("--chroma_persist_dir", default="./storage/vector_db")
    parser.add_argument("--collection_name", default="course_videos")
    parser.add_argument("--asr_backend", default="faster-whisper", choices=["faster-whisper", "openai-whisper"])
    parser.add_argument("--whisper_model", default="small")
    parser.add_argument("--embedding_timeout_sec", type=int, default=120)
    parser.add_argument("--embedding_max_retries", type=int, default=3)
    parser.add_argument("--gemini_dimensions", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()

    ingester = LocalVideoRAGIngester(
        embedding_api_base=args.embedding_api_base,
        embedding_api_key=args.embedding_api_key,
        embedding_model=args.embedding_model,
        embedding_backend=args.embedding_backend,
        chroma_persist_dir=args.chroma_persist_dir,
        collection_name=args.collection_name,
        temp_dir=args.temp_dir,
        window_seconds=args.window_seconds,
        stride_seconds=args.stride_seconds,
        asr_backend=args.asr_backend,
        whisper_model=args.whisper_model,
        embedding_timeout_sec=args.embedding_timeout_sec,
        embedding_max_retries=args.embedding_max_retries,
        gemini_dimensions=args.gemini_dimensions,
    )

    result = ingester.ingest(video_path=args.video_path, course_id=args.course_id)
    logging.info("Ingest done: %s", result)


if __name__ == "__main__":
    main()

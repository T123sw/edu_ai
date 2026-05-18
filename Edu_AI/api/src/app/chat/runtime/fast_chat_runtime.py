from __future__ import annotations

import base64
import hashlib
import mimetypes
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import time
import uuid

from core.config import Config


BASE_TEACHER_SYSTEM_PROMPT = """你是一位专业、耐心、善于启发的学科教师。你的目标不只是回答问题，还要帮助用户真正理解知识。
回答要求：1. 先直接回答用户当前的问题，先给出清晰结论、定义、解释或步骤，不要先说空泛套话。2. 回答要准确、条理清楚，必要时拆解概念、因果、步骤和易错点；适合时可以补充简短例子、类比或对比帮助理解。3. 如果用户的问题里存在误区、概念混淆或表述不严谨，先顺着用户的关注点回应，再温和纠正，不要居高临下。4. 在回答主体之后，结合当前问题提供2-3个自然延伸的学习方向，帮助用户继续学习，不要堆砌过多条目。5. 只在适合继续引导时，向用户提出 1 个简短、具体的反问，用于确认理解或引导下一步思考；如果当前问题更适合直接答复，就不要强行反问。6. 整体语气保持严谨、真诚、带适度鼓励，像真实教师，不要写成客服话术、工具说明或生硬摘要。"""


class FastChatRuntime:
    DEFAULT_VIDEO_FRAME_COUNT = 4

    def __init__(self, *, model_gateway, rag_retriever=None, web_retriever=None, video_retriever=None):
        self.model_gateway = model_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.video_retriever = video_retriever

    @staticmethod
    def _build_system_prompt(*, web_summary: str, rag_answer: str) -> str:
        prompt = BASE_TEACHER_SYSTEM_PROMPT
        if web_summary:
            prompt += (
                "\n你当前已经拿到了联网检索结果，请优先依据已经提供的联网信息作答，"
                "不要再说自己无法联网或不支持联网；如果联网信息与常识记忆冲突，以已经提供的联网结果为准。"
            )
        elif rag_answer:
            prompt += (
                "\n你当前已经拿到了知识库检索结果，请优先依据已经提供的检索信息作答，"
                "不要忽略这些参考信息；如果检索内容不足以支持结论，要明确说明边界，不要编造。"
            )
        return prompt

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(exclude_none=True))
        if hasattr(value, "__dict__"):
            return {
                key: raw
                for key, raw in vars(value).items()
                if not key.startswith("_") and raw is not None
            }
        return {}

    @staticmethod
    def _encode_image_to_data_url(image_path: str, mime_type: str | None = None) -> str:
        resolved = Path(str(image_path or "")).expanduser().resolve()
        file_bytes = resolved.read_bytes()
        mime = str(mime_type or "").strip() or mimetypes.guess_type(str(resolved))[0] or "image/png"
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:{mime};base64,{b64_data}"

    @staticmethod
    def _probe_video_duration_seconds(video_path: Path) -> float | None:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return None

        raw_duration = str(result.stdout or "").strip()
        if not raw_duration:
            return None
        try:
            duration = float(raw_duration)
        except ValueError:
            return None
        return duration if duration > 0 else None

    @staticmethod
    def _get_video_frame_cache_dir(video_path: Path) -> Path:
        stat = video_path.stat()
        cache_key = hashlib.sha1(
            f"{video_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
        ).hexdigest()[:16]
        cache_dir = (Config.STORAGE_ROOT / "chat_video_frames" / cache_key).resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _extract_video_frame_data_urls(
        self,
        video_path: str,
        mime_type: str | None = None,
        *,
        max_frames: int | None = None,
    ) -> list[str]:
        resolved = Path(str(video_path or "")).expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            return []

        cache_dir = self._get_video_frame_cache_dir(resolved)
        cached_frames = sorted(cache_dir.glob("frame_*.jpg"))
        if cached_frames:
            return [
                self._encode_image_to_data_url(str(frame_path), "image/jpeg")
                for frame_path in cached_frames
            ]

        frame_limit = max(1, int(max_frames or self.DEFAULT_VIDEO_FRAME_COUNT))
        duration = self._probe_video_duration_seconds(resolved)
        if duration is None:
            timestamps = [0.0]
        else:
            frame_count = min(frame_limit, max(1, int(duration // 10) + 1))
            timestamps = [
                duration * (index + 1) / (frame_count + 1)
                for index in range(frame_count)
            ]

        extracted_frames: list[Path] = []
        for index, timestamp in enumerate(timestamps):
            output_path = cache_dir / f"frame_{index:02d}.jpg"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        f"{max(0.0, timestamp):.3f}",
                        "-i",
                        str(resolved),
                        "-frames:v",
                        "1",
                        "-q:v",
                        "2",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
            except Exception:
                continue
            if output_path.exists() and output_path.stat().st_size > 0:
                extracted_frames.append(output_path)

        return [
            self._encode_image_to_data_url(str(frame_path), "image/jpeg")
            for frame_path in extracted_frames
        ]

    @staticmethod
    def _resolve_guarded_media_path(media_url: str) -> str:
        raw_url = str(media_url or "").strip()
        if not raw_url:
            return ""
        parsed = urlsplit(raw_url)
        encoded_path = parse_qs(parsed.query).get("path", [""])[0]
        relative_path = unquote(encoded_path).strip()
        if not relative_path:
            return ""

        route_path = parsed.path or ""
        if route_path.endswith("/api/rag/image") or route_path.endswith("/api/rag/media"):
            root = Config.STORAGE_ROOT.resolve()
        elif route_path.endswith("/api/chat/v2/images"):
            root = (Config.STORAGE_ROOT / "chat_images").resolve()
        elif route_path.endswith("/api/chat/v2/videos"):
            root = (Config.STORAGE_ROOT / "chat_videos").resolve()
        else:
            return ""

        resolved = (root / relative_path).resolve()
        if not str(resolved).startswith(str(root)):
            return ""
        return str(resolved)

    def _build_multimodal_user_content(
        self,
        *,
        question: str,
        context_text: str,
        input_images: list[Any],
        input_videos: list[Any],
        sources: list[Any],
    ) -> str | list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": context_text or question}]
        seen_paths: set[str] = set()

        for raw_image in list(input_images or []):
            image_meta = self._as_dict(raw_image)
            image_path = str(image_meta.get("storage_path") or image_meta.get("image_path") or "").strip()
            if not image_path or image_path in seen_paths:
                continue
            try:
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": self._encode_image_to_data_url(
                                image_path,
                                str(image_meta.get("mime_type") or "").strip() or None,
                            )
                        },
                    }
                )
                seen_paths.add(image_path)
            except Exception:
                continue

        for raw_video in list(input_videos or []):
            video_meta = self._as_dict(raw_video)
            video_path = str(video_meta.get("storage_path") or video_meta.get("video_path") or "").strip()
            if not video_path or video_path in seen_paths:
                continue
            try:
                frame_urls = self._extract_video_frame_data_urls(
                    video_path,
                    str(video_meta.get("mime_type") or "").strip() or None,
                )
                for frame_url in frame_urls:
                    blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": frame_url},
                        }
                    )
                if frame_urls:
                    seen_paths.add(video_path)
            except Exception:
                continue

        for raw_source in list(sources or []):
            source = self._as_dict(raw_source)
            modality = str(source.get("modality") or (source.get("metadata") or {}).get("modality") or "").strip().lower()
            if modality != "image":
                continue
            metadata = self._as_dict(source.get("metadata"))
            image_path = str(source.get("image_path") or metadata.get("image_path") or "").strip()
            if not image_path:
                image_url = str(source.get("image_url") or metadata.get("image_url") or "").strip()
                image_path = self._resolve_guarded_media_path(image_url)
            if not image_path or image_path in seen_paths:
                continue
            try:
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": self._encode_image_to_data_url(image_path)},
                    }
                )
                seen_paths.add(image_path)
            except Exception:
                continue

        return blocks if len(blocks) > 1 else (context_text or question)

    def _build_history_message_content(self, raw_message: Any) -> dict[str, Any] | None:
        message = self._as_dict(raw_message)
        role = str(message.get("role") or "").strip() or "user"
        content = message.get("content")

        if isinstance(content, list):
            return {"role": role, "content": content}

        text = str(content or "").strip()
        if role == "user":
            input_images = list(message.get("input_images") or [])
            input_videos = list(message.get("input_videos") or [])
            rendered = self._build_multimodal_user_content(
                question=text,
                context_text=text,
                input_images=input_images,
                input_videos=input_videos,
                sources=[],
            )
            if text or input_images or input_videos:
                return {"role": role, "content": rendered}
            return None

        if not text:
            return None
        return {"role": role, "content": text}

    def _prepare_generation(self, *, request, snapshot, decision):
        t_prep = time.perf_counter()
        recent_messages = list(getattr(snapshot, "recent_messages", []) or []) if snapshot is not None else []
        capability = getattr(request, "capability", None)
        sources: list[dict[str, Any]] = []
        context_blocks: list[str] = []
        web_summary = ""
        rag_answer = ""
        video_summary = ""
        web_trace: dict[str, Any] = {}

        # ── 并发检索：RAG / Web / Video 同时发起，取最慢的时间而非累加 ──
        _retrieval_futures: dict[str, Any] = {}
        _retrieval_timings: dict[str, float] = {}

        def _timed(label: str, fn, **kwargs):
            t = time.perf_counter()
            try:
                return label, fn(**kwargs), (time.perf_counter() - t) * 1000, None
            except Exception as exc:
                return label, None, (time.perf_counter() - t) * 1000, exc

        _retrieval_calls = []
        if self.rag_retriever is not None and bool(getattr(capability, "allow_rag", False)):
            _retrieval_calls.append(("rag", self.rag_retriever, {
                "query": request.question,
                "top_k": 5,
                "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
                "owner": getattr(request, "owner", None),
            }))
        if self.web_retriever is not None and bool(getattr(capability, "allow_web", False)):
            _retrieval_calls.append(("web", self.web_retriever, {
                "query": request.question,
                "owner": getattr(request, "owner", None),
            }))
        if self.video_retriever is not None and bool(getattr(capability, "allow_rag", False)):
            _retrieval_calls.append(("video", self.video_retriever, {
                "query": request.question,
                "top_k": 5,
                "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
                "owner": getattr(request, "owner", None),
            }))

        _raw_results: dict[str, Any] = {}
        if _retrieval_calls:
            t_retrieval = time.perf_counter()
            with ThreadPoolExecutor(max_workers=len(_retrieval_calls)) as _pool:
                _futures = {
                    _pool.submit(_timed, label, fn, **kwargs): label
                    for label, fn, kwargs in _retrieval_calls
                }
                for future in _futures:
                    label, result, elapsed_ms, exc = future.result()
                    _raw_results[label] = result
                    _retrieval_timings[label] = elapsed_ms
                    if exc:
                        print(f"[PREP] {label} 检索失败 {elapsed_ms:.0f}ms | {exc}", flush=True)
                    else:
                        print(f"[PREP] {label} 检索 {elapsed_ms:.0f}ms", flush=True)
            print(
                f"[PREP] 并发检索完成（挂钟） {(time.perf_counter() - t_retrieval) * 1000:.0f}ms",
                flush=True,
            )

        # ── 处理各路检索结果 ──
        if "rag" in _raw_results:
            rag_result = _raw_results["rag"]
            payload = dict((rag_result or {}).get("payload") or {}) if isinstance(rag_result, dict) else {}
            rag_sources = list(payload.get("sources") or [])
            rag_answer = str(payload.get("answer") or "").strip()
            if rag_answer:
                context_blocks.append(f"以下是知识库检索到的参考信息，请优先基于这些内容回答：\n{rag_answer}")
            sources.extend(rag_sources)

        if "web" in _raw_results:
            web_result = _raw_results["web"]
            payload = dict((web_result or {}).get("payload") or {}) if isinstance(web_result, dict) else {}
            web_sources = list(payload.get("sources") or [])
            web_summary = str(payload.get("summary") or payload.get("answer") or "").strip()
            web_trace = dict(payload.get("trace") or {})
            if web_summary:
                context_blocks.append(f"以下是联网检索到的参考信息，请结合这些内容回答：\n{web_summary}")
            sources.extend(web_sources)

        if "video" in _raw_results:
            video_result = _raw_results["video"]
            payload = dict((video_result or {}).get("payload") or {}) if isinstance(video_result, dict) else {}
            video_sources = list(payload.get("sources") or [])
            video_summary = str(payload.get("summary") or payload.get("answer") or "").strip()
            if video_summary:
                context_blocks.append(f"以下是视频检索到的参考信息，请结合这些内容回答：\n{video_summary}")
            sources.extend(video_sources)

        user_text = request.question
        if context_blocks:
            user_text = "\n\n".join([*context_blocks, f"用户问题：{request.question}"])

        user_content = self._build_multimodal_user_content(
            question=request.question,
            context_text=user_text,
            input_images=list(getattr(request, "input_images", []) or []),
            input_videos=list(getattr(request, "input_videos", []) or []),
            sources=sources,
        )

        system_content = self._build_system_prompt(
            web_summary=web_summary,
            rag_answer=rag_answer,
        )
        model_history_messages = [
            formatted_message
            for formatted_message in (
                self._build_history_message_content(raw_message)
                for raw_message in recent_messages
            )
            if formatted_message is not None
        ]

        messages = [
            {"role": "system", "content": system_content},
            *model_history_messages,
            {"role": "user", "content": user_content},
        ]
        t_total_prep = (time.perf_counter() - t_prep) * 1000
        action_name = getattr(decision, "action", "chat.reply") if decision is not None else "chat.reply"
        trace = {
            "trace_id": str(uuid.uuid4()),
            "path": "fast",
            "rag_used": bool(getattr(capability, "allow_rag", False) and self.rag_retriever is not None),
            "web_used": bool(getattr(capability, "allow_web", False) and self.web_retriever is not None),
            "video_used": bool(getattr(capability, "allow_rag", False) and self.video_retriever is not None),
            "input_image_count": len(list(getattr(request, "input_images", []) or [])),
            "input_video_count": len(list(getattr(request, "input_videos", []) or [])),
            "timings": {
                "prep_ms": round(t_total_prep),
                **{f"{k}_ms": round(v) for k, v in _retrieval_timings.items()},
                "llm_calls": [],
            },
        }
        if web_trace:
            trace.update(web_trace)
        if sources and trace.get("web_used"):
            trace["web_sources_count"] = len(sources)
        if video_summary:
            trace["video_summary_used"] = True

        print(
            f"[PREP] 准备完成 {t_total_prep:.0f}ms"
            f" | rag={trace['rag_used']} web={trace['web_used']}"
            f" | msgs={len(messages)}",
            flush=True,
        )
        return {
            "messages": messages,
            "sources": sources,
            "trace": trace,
            "action_name": action_name,
        }

    def _build_result(self, *, request, prepared: dict[str, Any], answer: str) -> dict[str, Any]:
        return {
            "message": {"role": "assistant", "content": answer},
            "conversation": {"conversation_id": getattr(request, "conversation_id", "") or ""},
            "action": {"name": prepared["action_name"]},
            "artifacts": [],
            "workflow": None,
            "sources": prepared["sources"],
            "trace": prepared["trace"],
        }

    def run(self, *, request, snapshot, decision):
        t_start = time.perf_counter()
        prepared = self._prepare_generation(request=request, snapshot=snapshot, decision=decision)
        t_llm = time.perf_counter()
        answer = self.model_gateway.chat(prepared["messages"])
        llm_ms = round((time.perf_counter() - t_llm) * 1000)
        total_ms = round((time.perf_counter() - t_start) * 1000)
        prepared["trace"]["timings"]["llm_calls"] = [{"stage": "fast.reply", "duration_ms": llm_ms, "retry": 0}]
        prepared["trace"]["timings"]["total_ms"] = total_ms
        return self._build_result(request=request, prepared=prepared, answer=answer)

    def run_stream(self, *, request, snapshot, decision):
        t_start = time.perf_counter()
        prepared = self._prepare_generation(request=request, snapshot=snapshot, decision=decision)
        yield {
            "type": "metadata",
            "payload": {
                "conversation_id": getattr(request, "conversation_id", "") or "",
                "sources": prepared["sources"],
                "trace": prepared["trace"],
            },
        }

        chunks: list[str] = []
        stream_chat = getattr(self.model_gateway, "stream_chat", None)
        t_llm = time.perf_counter()
        if callable(stream_chat):
            stream = stream_chat(prepared["messages"])
        else:
            stream = [self.model_gateway.chat(prepared["messages"])]

        for chunk in stream:
            text = str(chunk or "")
            if not text:
                continue
            chunks.append(text)
            yield {"type": "delta", "payload": {"content": text}}

        llm_ms = round((time.perf_counter() - t_llm) * 1000)
        total_ms = round((time.perf_counter() - t_start) * 1000)
        prepared["trace"]["timings"]["llm_calls"] = [{"stage": "fast.reply", "duration_ms": llm_ms, "retry": 0}]
        prepared["trace"]["timings"]["total_ms"] = total_ms

        answer = "".join(chunks)
        yield {
            "type": "result",
            "payload": self._build_result(request=request, prepared=prepared, answer=answer),
        }

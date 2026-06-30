from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import uuid

import httpx

from core import Config
from core.course_storage import CourseStorageManager, storage_manager as default_storage_manager


def _strip_extension(filename: str) -> str:
    text = str(filename or "").strip()
    if not text:
        return ""
    suffix = Path(text).suffix
    if suffix:
        return text[: -len(suffix)].strip()
    return text


def _join_url(base_url: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return httpx.URL(str(base_url or "").rstrip("/") + "/").join(text.lstrip("/")).__str__()


def _normalize_processing_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"success", "succeeded", "completed"}:
        return "completed"
    if normalized in {"failed", "error"}:
        return "failed"
    return "processing"


class OfflineTeachingVideoDisabledError(RuntimeError):
    pass


def is_offline_teaching_video_enabled() -> bool:
    value = os.getenv(
        "AI_LECTURER_OFFLINE_ENABLED",
        str(getattr(Config, "AI_LECTURER_OFFLINE_ENABLED", "1")),
    ).strip().lower()
    return value not in {"0", "false", "off", "no"}


def _extract_html2ppt_job_ref(deck_content: dict[str, Any]) -> tuple[str, str]:
    job_id = str(deck_content.get("job_id") or "").strip()
    revision_id = str(deck_content.get("revision_id") or "").strip()
    if job_id and revision_id:
        return job_id, revision_id

    for key in ("pptx_url", "html_full_url", "html_fragment_url", "manifest_url"):
        value = str(deck_content.get(key) or "").strip()
        match = re.search(r"/ppt/artifacts/([^/]+)/([^/]+)/", value)
        if match:
            return job_id or match.group(1), revision_id or match.group(2)
    return job_id, revision_id


def _extract_blocks_section(slide_body: str) -> str:
    match = re.search(r"(?ms)^### Blocks\s*$\n(.*?)(?=^### Notes\s*$|^---\s*$|\Z)", str(slide_body or ""))
    return str(match.group(1) if match else "").strip()


def _normalize_prompt_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*-\s*", "", line)
        line = re.sub(r"^\s*\d+\.\s*", "", line)
        line = re.sub(r"^(Left-Title|Right-Title|Step-Title|Title|Lead|Meta|Kind|URL)\s*:\s*", "", line)
        line = re.sub(r"^(Step-Text|Caption|Alt|Summary)\s*:\s*", "", line)
        line = line.strip()
        if line:
            lines.append(line)
    return lines


def parse_content_markdown_to_slide_prompts(markdown: str) -> list[str]:
    text = str(markdown or "").strip()
    if not text:
        return []

    pattern = re.compile(r"(?ms)^## Slide\s+(\d+)\s*$\n(.*?)(?=^---\s*$|^## Slide\s+\d+\s*$|\Z)")
    prompts: list[str] = []
    for match in pattern.finditer(text):
        slide_body = str(match.group(2) or "")
        role_match = re.search(r"(?m)^- Role:\s*(.+?)\s*$", slide_body)
        title_match = re.search(r"(?m)^- Title:\s*(.+?)\s*$", slide_body)
        role = str(role_match.group(1) if role_match else "").strip()
        title = str(title_match.group(1) if title_match else "").strip()
        block_lines = _normalize_prompt_lines(_extract_blocks_section(slide_body))

        lines: list[str] = []
        if title:
            lines.append(f"标题：{title}")
        if role:
            lines.append(f"页面角色：{role}")
        lines.extend(block_lines)
        prompt = "\n".join(line for line in lines if line).strip()
        if prompt:
            prompts.append(prompt)
    return prompts


def _outline_prompt_candidates(outline: Any) -> list[str]:
    if not isinstance(outline, dict):
        return []
    slides = list(outline.get("slides") or [])
    results: list[str] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        title = str(slide.get("title") or "").strip()
        goal = str(slide.get("goal") or "").strip()
        key_points = [str(item or "").strip() for item in list(slide.get("key_points") or []) if str(item or "").strip()]
        lines: list[str] = []
        if title:
            lines.append(f"标题：{title}")
        if goal:
            lines.append(goal)
        lines.extend(key_points)
        results.append("\n".join(line for line in lines if line).strip())
    return results


def build_slide_prompts(*, markdown: str, outline: Any, expected_count: int) -> list[str]:
    prompts = parse_content_markdown_to_slide_prompts(markdown)
    outline_fallbacks = _outline_prompt_candidates(outline)

    if expected_count <= 0:
        return prompts

    if len(prompts) < expected_count:
        for index in range(len(prompts), expected_count):
            if index < len(outline_fallbacks) and outline_fallbacks[index]:
                prompts.append(outline_fallbacks[index])
            else:
                prompts.append(f"第 {index + 1} 页")

    return prompts[:expected_count]


@dataclass
class PptAssetDownloader:
    base_timeout_seconds: float = 60.0

    def download(self, *, source_url: str, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=self.base_timeout_seconds, trust_env=False) as client:
            response = client.get(str(source_url or "").strip())
            response.raise_for_status()
            destination_path.write_bytes(response.content)
        return destination_path


class PowerPointSlideImageExporter:
    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = float(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(Config, "POWERPOINT_EXPORT_TIMEOUT_SEC", 120)
        )

    def export(self, *, pptx_path: Path, output_dir: Path) -> list[Path]:
        resolved_pptx = Path(pptx_path).resolve()
        resolved_output_dir = Path(output_dir).resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        script = textwrap.dedent(
            """
            param(
              [string]$PptxPath,
              [string]$OutputDir
            )

            $ErrorActionPreference = 'Stop'
            $powerpoint = $null
            $presentation = $null

            try {
              $powerpoint = New-Object -ComObject PowerPoint.Application
              $powerpoint.Visible = 1
              $presentation = $powerpoint.Presentations.Open($PptxPath, $true, $false, $false)
              $presentation.Export($OutputDir, 'PNG')
            }
            finally {
              if ($presentation -ne $null) { $presentation.Close() }
              if ($powerpoint -ne $null) { $powerpoint.Quit() }
            }
            """
        ).strip()

        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                    "-PptxPath",
                    str(resolved_pptx),
                    "-OutputDir",
                    str(resolved_output_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(self.timeout_seconds, 1.0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"PowerPoint slide image export timed out after {self.timeout_seconds:.0f}s. "
                "请确认本机 PowerPoint 没有弹窗阻塞，并尝试手动打开一次该 PPT。"
            ) from exc
        if completed.returncode != 0:
            stderr = str(completed.stderr or "").strip()
            stdout = str(completed.stdout or "").strip()
            details = "\n".join(part for part in [stderr, stdout] if part).strip()
            raise RuntimeError(
                "PowerPoint slide image export failed"
                + (f": {details}" if details else f" with exit code {completed.returncode}")
            )

        images = sorted(
            [*resolved_output_dir.glob("*.png"), *resolved_output_dir.glob("*.PNG")],
            key=lambda item: item.name.lower(),
        )
        if not images:
            raise RuntimeError("PowerPoint did not export any slide images.")
        return images


class HtmlDeckSlideImageExporter:
    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = float(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(Config, "POWERPOINT_EXPORT_TIMEOUT_SEC", 120)
        )

    def export(self, *, deck_html_path: Path, output_dir: Path) -> list[Path]:
        resolved_html = Path(deck_html_path).resolve()
        resolved_output_dir = Path(output_dir).resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        if not resolved_html.is_file():
            raise RuntimeError(f"HTML deck not found: {resolved_html}")

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is required to export slide images from deck.html.") from exc

        with sync_playwright() as playwright:
            browser = None
            launch_errors: list[str] = []
            for launch_kwargs in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
                try:
                    browser = playwright.chromium.launch(headless=True, **launch_kwargs)
                    break
                except Exception as exc:
                    launch_errors.append(str(exc))
            if browser is None:
                raise RuntimeError("Unable to launch a Chromium browser for deck.html export: " + " | ".join(launch_errors))

            try:
                page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
                page.goto(resolved_html.as_uri(), wait_until="networkidle", timeout=max(self.timeout_seconds, 1.0) * 1000)
                slide_count = page.locator(".slide").count()
                if slide_count <= 0:
                    raise RuntimeError("No .slide elements found in deck.html.")

                images: list[Path] = []
                for index in range(slide_count):
                    slide = page.locator(".slide").nth(index)
                    output_path = resolved_output_dir / f"slide-{index + 1:03d}.png"
                    slide.screenshot(path=str(output_path), timeout=max(self.timeout_seconds, 1.0) * 1000)
                    images.append(output_path)
                return images
            finally:
                browser.close()


@dataclass
class AiLecturerGatewayClient:
    base_url: str = str(getattr(Config, "AI_LECTURER_GATEWAY_URL", "http://127.0.0.1:8008"))
    timeout_seconds: float = 60.0

    def create_offline_video(self, *, course_title: str, pages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "course_title": str(course_title or "").strip() or "教学视频",
            "pages": pages,
        }
        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, trust_env=False) as client:
            response = client.post("/api/v1/offline/generate_full_video", json=payload)
            response.raise_for_status()
            data = response.json()

        task_id = str(data.get("task_id") or ((data.get("data") or {}).get("task_id")) or "").strip()
        video_url = str(data.get("video_url") or ((data.get("data") or {}).get("video_url")) or "").strip()
        return {
            "task_id": task_id,
            "status": str(data.get("status") or "processing").strip() or "processing",
            "video_url": _join_url(self.base_url, video_url) if video_url else "",
            "raw": data,
        }

    def create_offline_video_upload(self, *, course_title: str, pages: list[dict[str, str]]) -> dict[str, Any]:
        metadata_pages: list[dict[str, str]] = []
        file_handles: list[Any] = []
        files: list[tuple[str, tuple[str, Any, str]]] = []
        try:
            for index, page in enumerate(pages):
                image_path = Path(str(page.get("ppt_image_path") or "")).resolve()
                suffix = image_path.suffix or ".png"
                filename = f"slide-{index + 1:03d}{suffix}"
                metadata_pages.append(
                    {
                        "filename": filename,
                        "content_text": str(page.get("content_text") or "").strip(),
                    }
                )
                handle = image_path.open("rb")
                file_handles.append(handle)
                files.append(("files", (filename, handle, "image/png")))

            metadata = {
                "course_title": str(course_title or "").strip() or "教学视频",
                "pages": metadata_pages,
            }
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.post(
                    "/api/v1/offline/generate_full_video_upload",
                    data={"metadata": json.dumps(metadata, ensure_ascii=False)},
                    files=files,
                )
                response.raise_for_status()
                data = response.json()
        finally:
            for handle in file_handles:
                handle.close()

        task_id = str(data.get("task_id") or ((data.get("data") or {}).get("task_id")) or "").strip()
        video_url = str(data.get("video_url") or ((data.get("data") or {}).get("video_url")) or "").strip()
        return {
            "task_id": task_id,
            "status": str(data.get("status") or "processing").strip() or "processing",
            "video_url": _join_url(self.base_url, video_url) if video_url else "",
            "raw": data,
        }

    def get_offline_task_status(self, task_id: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, trust_env=False) as client:
            response = client.get(f"/api/v1/offline/status/{task_id}")
            response.raise_for_status()
            data = response.json()

        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        status = str(payload.get("status") or "").strip() or "processing"
        video_url = str(payload.get("video_url") or "").strip()
        error_message = str(payload.get("error") or payload.get("error_message") or data.get("detail") or "").strip()
        return {
            "task_id": str(task_id or "").strip(),
            "status": status,
            "video_url": _join_url(self.base_url, video_url) if video_url else "",
            "error_message": error_message,
            "raw": data,
        }


class AiLecturerProcessManager:
    def __init__(
        self,
        *,
        gateway_url: str | None = None,
        livetalking_url: str | None = None,
        entrypoint_path: str | Path | None = None,
        autostart: bool | None = None,
        startup_timeout_seconds: float | None = None,
    ) -> None:
        self.gateway_url = str(gateway_url or Config.AI_LECTURER_GATEWAY_URL).strip()
        self.livetalking_url = str(livetalking_url or Config.AI_LECTURER_LIVETALKING_URL).strip()
        self.entrypoint_path = Path(entrypoint_path or Config.AI_LECTURER_ENTRYPOINT).resolve()
        self.autostart = bool(
            autostart if autostart is not None else str(getattr(Config, "AI_LECTURER_AUTOSTART", "1")).strip() not in {"0", "false", "False"}
        )
        self.startup_timeout_seconds = float(
            startup_timeout_seconds if startup_timeout_seconds is not None else getattr(Config, "AI_LECTURER_STARTUP_TIMEOUT_SEC", 15.0)
        )
        self._process: subprocess.Popen[str] | None = None

    def _is_url_healthy(self, *, base_url: str, path: str) -> bool:
        try:
            with httpx.Client(base_url=base_url, timeout=2.0, trust_env=False) as client:
                response = client.get(path)
                response.raise_for_status()
            return True
        except Exception:
            return False

    def is_healthy(self) -> bool:
        return self._is_url_healthy(base_url=self.gateway_url, path="/openapi.json") and self._is_url_healthy(
            base_url=self.livetalking_url,
            path="/webrtcapi.html",
        )

    def ensure_started(self) -> bool:
        if self.is_healthy():
            return True
        if not self.autostart:
            return False
        if not self.entrypoint_path.exists():
            return False

        if self._process is None or self._process.poll() is not None:
            self._process = subprocess.Popen(
                [sys.executable, str(self.entrypoint_path)],
                cwd=str(self.entrypoint_path.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )

        deadline = time.time() + max(self.startup_timeout_seconds, 0.0)
        while time.time() < deadline:
            if self.is_healthy():
                return True
            if self._process is not None and self._process.poll() is not None:
                break
            time.sleep(0.5)
        return self.is_healthy()

    def launch_background(self) -> bool:
        """Fire-and-forget: start the subprocess without blocking on health checks."""
        if self.is_healthy():
            return True
        if not self.autostart:
            return False
        if not self.entrypoint_path.exists():
            return False
        if self._process is None or self._process.poll() is not None:
            self._process = subprocess.Popen(
                [sys.executable, str(self.entrypoint_path)],
                cwd=str(self.entrypoint_path.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        return True

    def shutdown(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass


class TeachingVideoBridgeService:
    def __init__(
        self,
        *,
        course_storage_manager: CourseStorageManager | None = None,
        ai_lecturer_client: Any | None = None,
        ppt_downloader: Any | None = None,
        slide_exporter: Any | None = None,
        html_slide_exporter: Any | None = None,
        task_root: Path | None = None,
        html2ppt_jobs_root: Path | None = None,
    ) -> None:
        self.course_storage_manager = course_storage_manager or default_storage_manager
        self.ai_lecturer_client = ai_lecturer_client or AiLecturerGatewayClient()
        self.ppt_downloader = ppt_downloader or PptAssetDownloader()
        self.slide_exporter = slide_exporter or PowerPointSlideImageExporter()
        self.html_slide_exporter = html_slide_exporter or HtmlDeckSlideImageExporter()
        self.task_root = Path(task_root or (Config.TEMP_DIR / "teaching_videos")).resolve()
        self.task_root.mkdir(parents=True, exist_ok=True)
        self.html2ppt_jobs_root = Path(html2ppt_jobs_root or Config.HTML2PPT_JOBS_ROOT).resolve()

    @staticmethod
    def _video_material_id(task_id: str) -> str:
        return f"teaching_video__{str(task_id or '').strip()}"

    def _get_ppt_material(self, course_id: str, ppt_material_id: str) -> dict[str, Any]:
        material = self.course_storage_manager.get_generated_material(course_id, "ppt", ppt_material_id)
        if not material:
            raise ValueError(f"PPT material not found: {ppt_material_id}")
        return material

    @staticmethod
    def _extract_deck_content(material: dict[str, Any]) -> dict[str, Any]:
        content = material.get("content")
        if not isinstance(content, dict):
            raise ValueError("Selected PPT does not have deck metadata.")
        return content

    def _read_html2ppt_content_markdown(self, deck_content: dict[str, Any]) -> str:
        job_id, revision_id = _extract_html2ppt_job_ref(deck_content)
        if not job_id or not revision_id:
            return ""

        try:
            root = self.html2ppt_jobs_root.resolve()
            revisions_dir = (root / job_id / "revisions").resolve()
            revisions_dir.relative_to(root)
        except Exception:
            return ""

        candidate_paths: list[Path] = []
        exact_path = (revisions_dir / revision_id / "content.md").resolve()
        candidate_paths.append(exact_path)
        if revisions_dir.is_dir():
            for revision_dir in sorted(revisions_dir.glob("rev_*"), reverse=True):
                candidate = (revision_dir / "content.md").resolve()
                if candidate != exact_path:
                    candidate_paths.append(candidate)

        for content_path in candidate_paths:
            try:
                content_path.relative_to(root)
            except Exception:
                continue
            if not content_path.is_file():
                continue
            try:
                content = content_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if content.strip():
                return content
        return ""

    def _resolve_content_markdown(self, deck_content: dict[str, Any]) -> str:
        direct_markdown = str(deck_content.get("content_markdown") or deck_content.get("markdown") or "")
        if direct_markdown.strip():
            return direct_markdown
        return self._read_html2ppt_content_markdown(deck_content)

    def resolve_material_content_markdown(self, material: dict[str, Any]) -> str:
        try:
            deck_content = self._extract_deck_content(material)
        except ValueError:
            return ""
        return self._resolve_content_markdown(deck_content)

    def _resolve_html_deck_path(self, deck_content: dict[str, Any]) -> Path | None:
        job_id, revision_id = _extract_html2ppt_job_ref(deck_content)
        if not job_id or not revision_id:
            return None
        try:
            root = self.html2ppt_jobs_root.resolve()
            deck_path = (root / job_id / "revisions" / revision_id / "deck.html").resolve()
            deck_path.relative_to(root)
        except Exception:
            return None
        if deck_path.is_file():
            return deck_path
        return None

    def list_available_ppts(self, course_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for material in self.course_storage_manager.list_generated_materials(course_id, material_type="ppt"):
            if not isinstance(material, dict):
                continue
            content = material.get("content")
            if not isinstance(content, dict):
                continue
            pptx_url = str(content.get("pptx_url") or "").strip()
            content_markdown = self._resolve_content_markdown(content).strip()
            status = str(((material.get("generation_state") or {}).get("status")) or "").strip().lower()
            if not pptx_url or not content_markdown or status != "completed":
                continue
            items.append(
                {
                    "material_id": str(material.get("material_id") or "").strip(),
                    "title": str(material.get("title") or "PPT").strip(),
                    "pptx_url": pptx_url,
                    "html_full_url": str(content.get("html_full_url") or "").strip() or None,
                    "slide_count": content.get("slide_count"),
                    "updated_at": str(material.get("updated_at") or material.get("created_at") or "").strip(),
                }
            )
        return items

    def _build_workspace(self, *, course_id: str) -> Path:
        workspace = self.task_root / str(course_id or "course").strip() / uuid.uuid4().hex[:12]
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _build_pages(self, *, workspace: Path, material: dict[str, Any]) -> list[dict[str, str]]:
        deck_content = self._extract_deck_content(material)
        pptx_url = str(deck_content.get("pptx_url") or "").strip()
        if not pptx_url:
            raise ValueError("Selected PPT is missing pptx_url.")

        content_markdown = self._resolve_content_markdown(deck_content).strip()
        if not content_markdown:
            raise ValueError("Selected PPT is missing content_markdown.")

        (workspace / "content.md").write_text(content_markdown, encoding="utf-8")

        deck_html_path = self._resolve_html_deck_path(deck_content)
        if deck_html_path is not None:
            slide_images = self.html_slide_exporter.export(
                deck_html_path=deck_html_path,
                output_dir=workspace / "slides",
            )
        else:
            pptx_path = self.ppt_downloader.download(
                source_url=pptx_url,
                destination_path=workspace / "source.pptx",
            )
            slide_images = self.slide_exporter.export(
                pptx_path=Path(pptx_path),
                output_dir=workspace / "slides",
            )
        prompts = build_slide_prompts(
            markdown=content_markdown,
            outline=material.get("outline"),
            expected_count=len(slide_images),
        )

        return [
            {
                "ppt_image_path": str(Path(image).resolve()),
                "content_text": str(prompts[index] or f"第 {index + 1} 页").strip(),
            }
            for index, image in enumerate(slide_images)
        ]

    def create_task(self, *, course_id: str, ppt_material_id: str, owner: str = "") -> dict[str, Any]:
        if not is_offline_teaching_video_enabled():
            raise OfflineTeachingVideoDisabledError(
                "Offline teaching video generation is disabled by "
                "AI_LECTURER_OFFLINE_ENABLED=0. Use real-time teaching playback "
                "or re-enable offline generation when CPU/GPU capacity is available."
            )

        material = self._get_ppt_material(course_id, ppt_material_id)
        workspace = self._build_workspace(course_id=course_id)
        pages = self._build_pages(workspace=workspace, material=material)

        course_title = _strip_extension(str(material.get("title") or "").strip()) or "教学视频"
        transfer_mode = str(getattr(Config, "AI_LECTURER_TRANSFER_MODE", "upload")).strip().lower()
        if transfer_mode == "path":
            task = self.ai_lecturer_client.create_offline_video(course_title=course_title, pages=pages)
        else:
            task = self.ai_lecturer_client.create_offline_video_upload(course_title=course_title, pages=pages)
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError("AI Lecturer did not return task_id.")

        material_id = self._video_material_id(task_id)
        now = datetime.now().isoformat()
        self.course_storage_manager.save_generated_material(
            course_id=course_id,
            material_type="video",
            material_id=material_id,
            material_data={
                "title": f"{course_title}-教学视频.mp4",
                "created_at": now,
                "updated_at": now,
                "content": {
                    "task_id": task_id,
                    "video_url": str(task.get("video_url") or "").strip() or None,
                    "source_ppt_material_id": ppt_material_id,
                    "workspace_dir": str(workspace),
                    "page_count": len(pages),
                    "owner": str(owner or "").strip() or None,
                },
                "generation_state": {
                    "status": _normalize_processing_status(task.get("status")),
                    "phase": "queued",
                    "message": "教学视频任务已提交",
                },
            },
        )

        return {
            "task_id": task_id,
            "material_id": material_id,
            "status": str(task.get("status") or "processing").strip() or "processing",
            "video_url": str(task.get("video_url") or "").strip() or None,
        }

    def _find_video_material_id(self, *, course_id: str, task_id: str) -> str | None:
        expected_id = self._video_material_id(task_id)
        if self.course_storage_manager.get_generated_material(course_id, "video", expected_id):
            return expected_id

        for material in self.course_storage_manager.list_generated_materials(course_id, material_type="video"):
            if not isinstance(material, dict):
                continue
            content = material.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("task_id") or "").strip() == str(task_id or "").strip():
                return str(material.get("material_id") or "").strip() or expected_id
        return None

    def get_task_status(self, *, course_id: str, task_id: str) -> dict[str, Any]:
        status = self.ai_lecturer_client.get_offline_task_status(task_id)
        material_id = self._find_video_material_id(course_id=course_id, task_id=task_id) or self._video_material_id(task_id)
        normalized_status = _normalize_processing_status(status.get("status"))
        error_message = str(status.get("error_message") or status.get("error") or "").strip()
        if normalized_status == "completed":
            status_phase = "completed"
            status_message = "教学视频生成完成"
        elif normalized_status == "failed":
            status_phase = "failed"
            status_message = error_message or "教学视频生成失败"
        else:
            status_phase = "polling"
            status_message = "教学视频生成中"

        self.course_storage_manager.save_generated_material(
            course_id=course_id,
            material_type="video",
            material_id=material_id,
            material_data={
                "content": {
                    "task_id": str(task_id or "").strip(),
                    "video_url": str(status.get("video_url") or "").strip() or None,
                    "error_message": error_message or None,
                },
                "generation_state": {
                    "status": normalized_status,
                    "phase": status_phase,
                    "message": status_message,
                },
            },
        )

        return {
            "task_id": str(task_id or "").strip(),
            "material_id": material_id,
            "status": str(status.get("status") or "").strip() or "processing",
            "video_url": str(status.get("video_url") or "").strip() or None,
            "error_message": error_message or None,
        }


_teaching_video_bridge_service: TeachingVideoBridgeService | None = None
_ai_lecturer_process_manager: AiLecturerProcessManager | None = None


def get_teaching_video_bridge_service() -> TeachingVideoBridgeService:
    global _teaching_video_bridge_service
    if _teaching_video_bridge_service is None:
        _teaching_video_bridge_service = TeachingVideoBridgeService()
    return _teaching_video_bridge_service


def get_ai_lecturer_process_manager() -> AiLecturerProcessManager:
    global _ai_lecturer_process_manager
    if _ai_lecturer_process_manager is None:
        _ai_lecturer_process_manager = AiLecturerProcessManager()
    return _ai_lecturer_process_manager

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


def _safe_target(base: Path, relative: str) -> Path:
    candidate = (base / relative).resolve()
    candidate.relative_to(base.resolve())
    return candidate


def _download_image(session: requests.Session, url: str, referer: str) -> bytes:
    last_error = None
    for attempt in range(5):
        try:
            response = session.get(url, headers={"Referer": referer}, timeout=45)
            content_type = str(response.headers.get("content-type") or "").lower()
            if response.status_code == 200 and content_type.startswith("image/"):
                if len(response.content) > 15 * 1024 * 1024:
                    raise ValueError("图片超过 15MB")
                return response.content
            last_error = RuntimeError(f"status={response.status_code}, content_type={content_type}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < 4:
            time.sleep(min(8.0, 0.5 * (2**attempt)))
    raise RuntimeError(f"图片下载失败: {url}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="在影子区修复旧开放教材资料的本地图表")
    parser.add_argument("--mapping", type=Path, default=Path("evaluation/reports/2026-08-08-legacy-to-v2-mapping.json"))
    parser.add_argument("--course-dir", type=Path, default=Path("../course_data/courses/computational-thinking"))
    parser.add_argument("--output-root", type=Path, default=Path("evaluation/shadow/computational-thinking-v2/legacy-repaired/v1"))
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    course_index = json.loads((args.course_dir / "knowledge_base" / "index.json").read_text(encoding="utf-8"))
    by_id = {str(item.get("id") or ""): item for item in course_index}
    documents_dir = args.output_root / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    failures = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (EduAI Course Knowledge Builder)"})

    selected = [
        (node_id, document)
        for node_id, value in (mapping.get("node_materials") or {}).items()
        for document in (value.get("documents") or [])[:3]
    ]
    for index, (node_id, mapped) in enumerate(selected, start=1):
        document_id = str(mapped.get("document_id") or "")
        record = by_id.get(document_id) or {}
        source_path = args.course_dir / str(mapped.get("path") or "")
        filename = str(mapped.get("path") or source_path.name).replace("\\", "/").split("/")[-1]
        destination = documents_dir / filename
        print(f"[LegacyRepair] {index}/{len(selected)} {filename}")
        try:
            text = source_path.read_text(encoding="utf-8")
            source_url = str(record.get("source_url") or mapped.get("source_url") or "")
            source_host = urlparse(source_url).netloc.casefold()
            linked_assets = []
            for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
                target = match.group(1).strip().split("#", 1)[0].split("?", 1)[0]
                if not target or target.startswith(("http://", "https://", "data:")):
                    continue
                asset_path = _safe_target(documents_dir, target)
                if not asset_path.exists():
                    if source_host.endswith("hello-algo.com"):
                        asset_url = urljoin(source_url, f"../{target}")
                    else:
                        asset_url = urljoin(source_url, target)
                    data = _download_image(session, asset_url, source_url)
                    asset_path.parent.mkdir(parents=True, exist_ok=True)
                    asset_path.write_bytes(data)
                    time.sleep(0.05)
                linked_assets.append(
                    {
                        "relative_path": str(asset_path.relative_to(documents_dir.resolve())).replace("\\", "/"),
                        "content_type": mimetypes.guess_type(asset_path.name)[0] or "image/*",
                        "size": asset_path.stat().st_size,
                    }
                )
            destination.write_text(text, encoding="utf-8")
            manifest.append(
                {
                    "id": f"repaired-{document_id}",
                    "legacy_document_id": document_id,
                    "filename": filename,
                    "path": str(destination.relative_to(args.output_root)).replace("\\", "/"),
                    "scope_type": "knowledge_point",
                    "scope_id": node_id,
                    "library_type": "course",
                    "source_url": source_url,
                    "source_title": record.get("source_title") or mapped.get("title"),
                    "source_site_name": record.get("source_site_name"),
                    "source_license": record.get("source_license"),
                    "source_license_url": record.get("source_license_url"),
                    "source_revision": record.get("source_revision"),
                    "source_language": record.get("source_language"),
                    "content_language": record.get("content_language") or mapped.get("language"),
                    "authority_tier": record.get("authority_tier") or mapped.get("authority_tier"),
                    "linked_assets": linked_assets,
                    "status": "staged",
                }
            )
        except Exception as exc:
            failures.append({"document_id": document_id, "scope_id": node_id, "error": str(exc)})

    payload = {
        "builder": "legacy-media-repair-v1",
        "status": "staged" if not failures else "partially_staged",
        "document_count": len(manifest),
        "failure_count": len(failures),
        "failures": failures,
        "documents": manifest,
    }
    (args.output_root / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**payload, "documents": "omitted"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# DeepSearch Web Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make deep-search imported web documents display as `site_name + full-width bar + page_title` and show a favicon-backed site logo in the teacher knowledge base.

**Architecture:** Add a shared backend helper that normalizes web-source metadata from URL, title, and crawl metadata, then reuse it from both deep-search ingestion entry points. Expose the new metadata through the RAG document list surface and render it in the teacher source panel through a small extracted frontend helper with node-based tests.

**Tech Stack:** Python, FastAPI, Pydantic, existing RAG runtime, React, TypeScript, Ant Design, `node:test`, `pytest`

---

## File Structure

- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py`
  Purpose: apply normalized web metadata in the API-driven deep-search import flow.

- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py`
  Purpose: apply the same normalized web metadata in the tool-driven deep-search import flow.

- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/web_source_metadata.py`
  Purpose: single-responsibility helper for deriving `source_site_name`, `source_logo_url`, and readable web `file_name`.

- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py`
  Purpose: unit tests for site-name, display-name, and favicon fallback logic.

- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py`
  Purpose: regression tests that prove imported web records persist the new metadata.

- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py`
  Purpose: extend `DocumentInfo` and related response models with `source_site_name` and `source_logo_url`.

- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py`
  Purpose: include `source_site_name` and `source_logo_url` in `RAGSystem.list_documents()`.

- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py`
  Purpose: lock the new API fields into the compatibility surface.

- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py`
  Purpose: prove `RAGSystem.list_documents()` serializes the new web fields.

- Modify: `D:/Edu_AI_1/Edu_AI/src/services/rag.ts`
  Purpose: add `source_site_name` and `source_logo_url` to the `KnowledgeDocument` interface.

- Create: `D:/Edu_AI_1/Edu_AI/src/components/teacher/sourcePanel.webDoc.helpers.ts`
  Purpose: extracted pure helper for source-panel web labels and icon decisions.

- Modify: `D:/Edu_AI_1/Edu_AI/src/components/teacher/SourcePanel.tsx`
  Purpose: render favicon-based logos for web documents and keep existing fallbacks for older data.

- Create: `D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts`
  Purpose: node-based tests for frontend label and logo fallback behavior.

## Task 1: Build the Shared Web Metadata Helper

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/web_source_metadata.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py`

- [ ] **Step 1: Write the failing helper tests**

```python
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.web_source_metadata import build_web_source_metadata


def test_build_web_source_metadata_prefers_explicit_site_name_and_favicon():
    result = build_web_source_metadata(
        url="https://en.wikipedia.org/wiki/Li_Bai",
        page_title="Li Bai - Wikipedia",
        metadata={
            "site_name": "Wikipedia",
            "icon_href": "/static/favicon/wikipedia.ico",
        },
    )

    assert result["source_site_name"] == "Wikipedia"
    assert result["source_logo_url"] == "https://en.wikipedia.org/static/favicon/wikipedia.ico"
    assert result["file_name"] == "Wikipedia\uFF5CLi Bai - Wikipedia"


def test_build_web_source_metadata_falls_back_to_host_favicon():
    result = build_web_source_metadata(
        url="https://example.com/articles/test",
        page_title="Example article",
        metadata={},
    )

    assert result["source_site_name"] == "example.com"
    assert result["source_logo_url"] == "https://example.com/favicon.ico"
    assert result["file_name"] == "example.com｜Example article"


def test_build_web_source_metadata_avoids_duplicate_site_prefix():
    result = build_web_source_metadata(
        url="https://openai.com/index/introducing-gpt",
        page_title="OpenAI",
        metadata={"site_name": "OpenAI"},
    )

    assert result["file_name"] == "OpenAI"
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.web_source_metadata'`.

- [ ] **Step 3: Write the minimal helper implementation**

```python
from __future__ import annotations

import re
from typing import Any, Dict
from urllib.parse import urljoin, urlparse


_FULL_WIDTH_BAR = "\uFF5C"
_ICON_KEYS = ("icon_href", "shortcut_icon_href", "apple_touch_icon_href")
_SITE_NAME_KEYS = ("site_name", "og_site_name", "source_site_name")


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text


def _safe_display_text(value: str) -> str:
    text = _clean_text(value)
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    return _clean_text(text)


def _hostname(url: str) -> str:
    return (urlparse(url).netloc or "").strip().lower()


def _derive_site_name(page_title: str, metadata: Dict[str, Any], url: str) -> str:
    for key in _SITE_NAME_KEYS:
        candidate = _safe_display_text(str(metadata.get(key) or ""))
        if candidate:
            return candidate

    title = _safe_display_text(page_title)
    for separator in (" | ", " - ", "_"):
        if separator in title:
            parts = [part.strip() for part in title.split(separator) if part.strip()]
            if len(parts) >= 2:
                return parts[-1]

    return _hostname(url) or "web"


def _resolve_logo_url(url: str, metadata: Dict[str, Any]) -> str | None:
    for key in _ICON_KEYS:
        raw_value = str(metadata.get(key) or "").strip()
        if raw_value:
            return urljoin(url, raw_value)

    host = _hostname(url)
    if not host:
        return None

    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}/favicon.ico"


def build_web_source_metadata(*, url: str, page_title: str, metadata: Dict[str, Any] | None = None) -> Dict[str, str | None]:
    raw_metadata = dict(metadata or {})
    title = _safe_display_text(page_title) or _hostname(url) or "untitled"
    site_name = _derive_site_name(title, raw_metadata, url)
    logo_url = _resolve_logo_url(url, raw_metadata)

    if site_name and title and site_name.casefold() != title.casefold():
        file_name = f"{site_name}{_FULL_WIDTH_BAR}{title}"
    else:
        file_name = site_name or title

    return {
        "file_name": file_name,
        "source_site_name": site_name or None,
        "source_logo_url": logo_url,
    }
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py -q`

Expected: PASS with `3 passed`.

- [ ] **Step 5: Commit the helper task**

```bash
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/web_source_metadata.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py
git commit -m "feat: add deepsearch web metadata helper"
```

## Task 2: Apply the Helper to Both Deep-Search Import Flows

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py`
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py`

- [ ] **Step 1: Write the failing ingestion regression test**

```python
import sys
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import deepsearch_pipeline


def test_run_deepsearch_pipeline_persists_site_name_and_logo(monkeypatch, tmp_path):
    url = "https://en.wikipedia.org/wiki/Li_Bai"
    resolved = SimpleNamespace(index_key="idx-1", source_key="source-1", record={})

    monkeypatch.setattr(deepsearch_pipeline, "deepsearch_large_llm", lambda query: {"links": [url]})
    monkeypatch.setattr(
        deepsearch_pipeline,
        "get_crawler_service",
        lambda: SimpleNamespace(
            crawl_urls=lambda **kwargs: SimpleNamespace(
                total_urls=1,
                success_count=1,
                failed_count=0,
                results=[
                    SimpleNamespace(
                        status="success",
                        url=url,
                        title="Li Bai - Wikipedia",
                        content="A" * 400,
                        content_type="text",
                        file_path=None,
                        metadata={"site_name": "Wikipedia"},
                    )
                ],
            )
        ),
    )
    monkeypatch.setattr(
        deepsearch_pipeline,
        "ContentCleaner",
        lambda: SimpleNamespace(clean_text_content=lambda content, file_path: {"cleaned_content": content, "metadata": {}}),
    )
    monkeypatch.setattr(
        deepsearch_pipeline,
        "get_storage_service",
        lambda: SimpleNamespace(save_crawl_batch=lambda batch: "batch-1"),
    )
    monkeypatch.setattr(
        deepsearch_pipeline,
        "get_rag_system",
        lambda: SimpleNamespace(import_document=lambda *args, **kwargs: {"status": "success"}, _save_index=lambda: None),
    )
    monkeypatch.setattr(deepsearch_pipeline, "resolve_rag_document", lambda *args, **kwargs: resolved)
    monkeypatch.setattr(deepsearch_pipeline.Config, "DOCUMENTS_ROOT", tmp_path)

    result = deepsearch_pipeline.run_deepsearch_pipeline(query="Li Bai", owner="teacher-a")

    assert result["ok"] is True
    assert resolved.record["file_name"] == "Wikipedia\uFF5CLi Bai - Wikipedia"
    assert resolved.record["source_site_name"] == "Wikipedia"
    assert resolved.record["source_logo_url"] == "https://en.wikipedia.org/favicon.ico"
```

- [ ] **Step 2: Run the ingestion test to verify it fails**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py -q`

Expected: FAIL because `source_site_name` and `source_logo_url` are not written into `resolved.record`.

- [ ] **Step 3: Wire the helper into both import code paths**

```python
from app.web_source_metadata import build_web_source_metadata


web_meta = build_web_source_metadata(
    url=url,
    page_title=title,
    metadata=r.metadata,
)

pretty_name = web_meta["file_name"] or title
rec["file_name"] = pretty_name
rec["source_url"] = url
rec["source_title"] = title
rec["source_domain"] = domain
rec["source_site_name"] = web_meta["source_site_name"]
rec["source_logo_url"] = web_meta["source_logo_url"]
rec["doc_kind"] = "web"
```

Apply the same block in both import loops:
- `run_deepsearch_pipeline()` in `deepsearch_pipeline.py`
- `deepsearch_and_crawl()` in `deepsearch.py`

- [ ] **Step 4: Run the ingestion test to verify it passes**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 5: Run the nearby deep-search regression tests**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_tool_registry.py -q`

Expected: PASS and existing web-search tool behavior remains green.

- [ ] **Step 6: Commit the deep-search integration task**

```bash
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py
git commit -m "feat: apply normalized metadata to deepsearch imports"
```

## Task 3: Expose the New Fields Through the RAG API Surface

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py`
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py`

- [ ] **Step 1: Write the failing API-surface tests**

```python
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from rag_v2.rag_main.api import DocumentInfo
from rag_v2.rag_main.system import RAGSystem


def test_document_info_exposes_web_logo_fields():
    assert "source_site_name" in DocumentInfo.model_fields
    assert "source_logo_url" in DocumentInfo.model_fields


def test_list_documents_returns_web_logo_fields():
    rag_system = RAGSystem.__new__(RAGSystem)
    rag_system.document_index = {
        "user_teacher-a:web.md": {
            "file_name": "Wikipedia\uFF5CLi Bai - Wikipedia",
            "include_in_search": True,
            "chunk_count": 3,
            "owner": "teacher-a",
            "source_url": "https://en.wikipedia.org/wiki/Li_Bai",
            "source_title": "Li Bai - Wikipedia",
            "source_domain": "en.wikipedia.org",
            "source_site_name": "Wikipedia",
            "source_logo_url": "https://en.wikipedia.org/favicon.ico",
            "doc_kind": "web",
        }
    }

    docs = rag_system.list_documents(owner="teacher-a")

    assert docs[0]["source_site_name"] == "Wikipedia"
    assert docs[0]["source_logo_url"] == "https://en.wikipedia.org/favicon.ico"
    assert docs[0]["doc_kind"] == "web"
```

- [ ] **Step 2: Run the API-surface tests to verify they fail**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py -q`

Expected: FAIL because `DocumentInfo` and `RAGSystem.list_documents()` do not yet include the new fields.

- [ ] **Step 3: Add the fields to the response model and serializer**

```python
class DocumentInfo(BaseModel):
    file_path: str
    file_name: str
    include_in_search: bool
    chunk_count: int
    image_chunk_count: int = 0
    imported_at: Optional[str] = None
    summary: Optional[str] = None
    summary_updated_at: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    hash: Optional[str] = None
    owner: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_domain: Optional[str] = None
    source_site_name: Optional[str] = None
    source_logo_url: Optional[str] = None
    doc_kind: Optional[str] = None
    modality: Optional[str] = None
    image_url: Optional[str] = None
```

```python
documents.append(
    {
        "file_path": file_path,
        "file_name": metadata.get("file_name") or Path(file_path).name,
        "include_in_search": metadata.get("include_in_search", True),
        "chunk_count": metadata.get("chunk_count", 0),
        "image_chunk_count": metadata.get("image_chunk_count", 0),
        "imported_at": metadata.get("imported_at"),
        "summary": metadata.get("summary"),
        "summary_updated_at": metadata.get("summary_updated_at"),
        "file_size": metadata.get("file_size"),
        "page_count": metadata.get("page_count"),
        "hash": metadata.get("hash"),
        "owner": metadata.get("owner"),
        "source_url": metadata.get("source_url"),
        "source_title": metadata.get("source_title"),
        "source_domain": metadata.get("source_domain"),
        "source_site_name": metadata.get("source_site_name"),
        "source_logo_url": metadata.get("source_logo_url"),
        "doc_kind": metadata.get("doc_kind"),
    }
)
```

- [ ] **Step 4: Run the API-surface tests to verify they pass**

Run: `pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py -q`

Expected: PASS with all tests green.

- [ ] **Step 5: Commit the RAG surface task**

```bash
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py
git commit -m "feat: expose deepsearch web metadata in rag api"
```

## Task 4: Render Web Logos in the Teacher Source Panel

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/rag.ts`
- Create: `D:/Edu_AI_1/Edu_AI/src/components/teacher/sourcePanel.webDoc.helpers.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/src/components/teacher/SourcePanel.tsx`
- Create: `D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts`

- [ ] **Step 1: Write the failing frontend helper test**

```ts
import assert from 'node:assert/strict';

import {
  buildSourcePanelDisplayTitle,
  getWebDocumentLogoUrl,
} from '../../src/components/teacher/sourcePanel.webDoc.helpers.ts';

const richWebDoc = {
  file_name: 'Wikipedia\uFF5CLi Bai - Wikipedia',
  source_title: 'Li Bai - Wikipedia',
  source_site_name: 'Wikipedia',
  source_logo_url: 'https://en.wikipedia.org/favicon.ico',
  source_url: 'https://en.wikipedia.org/wiki/Li_Bai',
  doc_kind: 'web',
};

assert.equal(buildSourcePanelDisplayTitle(richWebDoc as any), 'Wikipedia\uFF5CLi Bai - Wikipedia');
assert.equal(getWebDocumentLogoUrl(richWebDoc as any), 'https://en.wikipedia.org/favicon.ico');

const legacyWebDoc = {
  file_name: 'web_en.wikipedia.org_li-bai_a1b2c3.md',
  source_title: 'Li Bai - Wikipedia',
  source_domain: 'en.wikipedia.org',
  source_url: 'https://en.wikipedia.org/wiki/Li_Bai',
  doc_kind: 'web',
};

assert.equal(buildSourcePanelDisplayTitle(legacyWebDoc as any), 'Li Bai - Wikipedia');
assert.equal(getWebDocumentLogoUrl(legacyWebDoc as any), undefined);

console.log('sourcePanel.webDoc.helpers tests passed');
```

- [ ] **Step 2: Run the frontend helper test to verify it fails**

Run: `node --test D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts`

Expected: FAIL with `Cannot find module '../../src/components/teacher/sourcePanel.webDoc.helpers.ts'`.

- [ ] **Step 3: Create the frontend helper and wire it into SourcePanel**

```ts
export function buildSourcePanelDisplayTitle(doc: {
  file_name?: string;
  source_title?: string;
  source_site_name?: string;
  source_domain?: string;
  source_url?: string;
  doc_kind?: string;
}): string {
  if (doc.doc_kind === 'web' && doc.file_name) {
    return doc.file_name;
  }

  if (doc.source_title) {
    return doc.source_title;
  }

  if (doc.source_site_name) {
    return doc.source_site_name;
  }

  if (doc.source_domain) {
    return `${doc.source_domain} - 网页内容`;
  }

  return doc.file_name || '未命名';
}


export function getWebDocumentLogoUrl(doc: {
  doc_kind?: string;
  source_logo_url?: string;
}): string | undefined {
  if (doc.doc_kind !== 'web') {
    return undefined;
  }

  return doc.source_logo_url || undefined;
}
```

```tsx
const logoUrl = getWebDocumentLogoUrl(doc);

return {
  key: doc.file_path,
  title: decodeDisplayText(buildSourcePanelDisplayTitle(doc)),
  type: isImage ? 'image' : 'file',
  filePath: doc.file_path,
  imageUrl: doc.image_url,
  logoUrl,
};
```

```tsx
<span className="source-panel__item-icon">
  {file.logoUrl ? (
    <img
      src={file.logoUrl}
      alt=""
      width={16}
      height={16}
      onError={(event) => {
        event.currentTarget.style.display = 'none';
        const fallback = event.currentTarget.nextElementSibling as HTMLElement | null;
        if (fallback) fallback.style.display = 'inline-flex';
      }}
    />
  ) : null}
  <span style={{ display: file.logoUrl ? 'none' : 'inline-flex' }}>
    {getFileIcon(file.type, file.title, 16)}
  </span>
</span>
```

- [ ] **Step 4: Extend the frontend data model**

```ts
export interface KnowledgeDocument {
  file_path: string;
  file_name: string;
  include_in_search: boolean;
  chunk_count: number;
  image_chunk_count?: number;
  imported_at?: string;
  summary?: string;
  summary_updated_at?: string;
  file_size?: number;
  page_count?: number;
  hash?: string;
  owner?: string;
  source_url?: string;
  source_title?: string;
  source_domain?: string;
  source_site_name?: string;
  source_logo_url?: string;
  doc_kind?: string;
  modality?: string;
  image_url?: string;
}
```

- [ ] **Step 5: Run the frontend helper test and the frontend build**

Run: `node --test D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts`

Expected: PASS and prints `sourcePanel.webDoc.helpers tests passed`.

Run: `cmd /c "cd /d D:\Edu_AI_1\Edu_AI && npm run build"`

Expected: PASS with Vite production build completed.

- [ ] **Step 6: Commit the frontend task**

```bash
git add D:/Edu_AI_1/Edu_AI/src/services/rag.ts D:/Edu_AI_1/Edu_AI/src/components/teacher/sourcePanel.webDoc.helpers.ts D:/Edu_AI_1/Edu_AI/src/components/teacher/SourcePanel.tsx D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts
git commit -m "feat: show web logos in teacher source panel"
```

## Final Verification

- [ ] Run the focused backend suite:

```bash
pytest D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_tool_registry.py -q
```

Expected: PASS with all selected backend tests green.

- [ ] Run the focused frontend verification:

```bash
node --test D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts
cmd /c "cd /d D:\Edu_AI_1\Edu_AI && npm run build"
```

Expected: PASS for both commands.

- [ ] Create the integration commit:

```bash
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/web_source_metadata.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_web_metadata.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_deepsearch_pipeline_web_import.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_compat_surface.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_web_document_fields.py D:/Edu_AI_1/Edu_AI/src/services/rag.ts D:/Edu_AI_1/Edu_AI/src/components/teacher/sourcePanel.webDoc.helpers.ts D:/Edu_AI_1/Edu_AI/src/components/teacher/SourcePanel.tsx D:/Edu_AI_1/Edu_AI/tests/frontend/sourcePanel.webDoc.helpers.test.ts
git commit -m "feat: improve deepsearch web document metadata"
```

# rag_v2 Backend Compat Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `new_rag` runtime entrypoints with a `rag_v2` compatibility layer that uses the new RAG implementation while keeping existing backend call patterns stable.

**Architecture:** Create a real runtime package under `rag_v2/rag_main/` by normalizing the current `rag_v2/rag-main/` source into import-safe package-relative modules. Build a compatibility surface in `rag_v2/api.py` and `rag_v2/system.py` that preserves the current `new_rag` route set and `get_rag_system()` object expectations, then switch all backend imports from `new_rag.api` to `rag_v2.api` in one pass.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, existing `RAGSystem`/Chroma-based backend modules

---

### Task 1: Create an import-safe rag_v2 runtime package

**Files:**
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/__init__.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/core/__init__.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/core/config.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/app/__init__.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/rag_main/app/auth.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_runtime_import.py`

- [ ] **Step 1: Write the failing import test**

```python
from rag_v2.rag_main import api as runtime_api
from rag_v2.rag_main.system import RAGSystem


def test_rag_v2_runtime_package_can_be_imported():
    assert runtime_api.router.prefix == "/api/rag"
    assert RAGSystem is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_runtime_import.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'rag_v2.rag_main'`

- [ ] **Step 3: Create the runtime package structure and normalize imports**

```python
# Edu_AI/api/Edu_AI/rag_v2/rag_main/__init__.py
from .system import RAGSystem

__all__ = ["RAGSystem"]
```

```python
# Edu_AI/api/Edu_AI/rag_v2/rag_main/api.py
from .system import RAGSystem
from .core.config import Config
from app.auth import get_current_user
```

```python
# Edu_AI/api/Edu_AI/rag_v2/rag_main/system.py
from .core.config import Config
```

```python
# Edu_AI/api/Edu_AI/rag_v2/rag_main/core/__init__.py
from .config import Config

__all__ = ["Config"]
```

Implementation notes:
- Copy the current `rag_v2/rag-main/` runtime sources into `rag_v2/rag_main/` instead of importing from the hyphenated directory directly.
- Keep the current code behavior intact; only normalize package layout and import statements needed for safe loading inside the host backend.
- Do not delete `rag_v2/rag-main/`; treat it as the raw source snapshot.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_runtime_import.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/rag_v2/rag_main Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_runtime_import.py
git commit -m "feat: create import-safe rag_v2 runtime package"
```

### Task 2: Add the rag_v2 compatibility API surface

**Files:**
- Create: `Edu_AI/api/Edu_AI/rag_v2/api.py`
- Create: `Edu_AI/api/Edu_AI/rag_v2/system.py`
- Modify: `Edu_AI/api/Edu_AI/rag_v2/__init__.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_api_compat.py`

- [ ] **Step 1: Write the failing compatibility test**

```python
from rag_v2 import RAGSystem, get_rag_system, rag_router


def test_rag_v2_exports_match_new_rag_entrypoints():
    assert RAGSystem is not None
    assert callable(get_rag_system)
    assert rag_router.prefix == "/api/rag"
```

```python
from rag_v2.api import router


def test_rag_v2_router_does_not_expose_unapproved_new_routes():
    paths = {route.path for route in router.routes}
    assert "/api/rag/query" in paths
    assert "/api/rag/import" in paths
    assert "/api/rag/query_stream" not in paths
    assert "/api/rag/import_image" not in paths
    assert "/api/rag/import_video" not in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_api_compat.py -v`  
Expected: FAIL because `rag_v2.__init__` does not export the compatibility objects yet

- [ ] **Step 3: Implement the compatibility wrapper**

```python
# Edu_AI/api/Edu_AI/rag_v2/system.py
from .rag_main.system import RAGSystem

__all__ = ["RAGSystem"]
```

```python
# Edu_AI/api/Edu_AI/rag_v2/api.py
from .rag_main.api import get_rag_system as _get_runtime_rag_system
from .rag_main.api import (
    delete_document,
    get_document_details,
    get_document_summary,
    get_import_progress,
    get_rag_image,
    import_document,
    import_document_from_path,
    list_documents,
    rag_query,
    rename_document,
    router,
    stats,
    update_document_participation,
    upload_temp,
)


def get_rag_system():
    return _get_runtime_rag_system()
```

```python
# Edu_AI/api/Edu_AI/rag_v2/__init__.py
from .api import get_rag_system
from .api import router as rag_router
from .system import RAGSystem

__all__ = ["RAGSystem", "rag_router", "get_rag_system"]
```

Implementation notes:
- Do not re-export the whole runtime router blindly if it includes unapproved phase-2 routes.
- Build a compatibility router in `rag_v2/api.py` that only registers the route handlers already allowed by the spec.
- Keep the public names aligned with `new_rag`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_api_compat.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/rag_v2/__init__.py Edu_AI/api/Edu_AI/rag_v2/api.py Edu_AI/api/Edu_AI/rag_v2/system.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_api_compat.py
git commit -m "feat: add rag_v2 compatibility api surface"
```

### Task 3: Switch the FastAPI main entrypoint to rag_v2

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/main.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_main_entrypoint.py`

- [ ] **Step 1: Write the failing entrypoint test**

```python
from pathlib import Path


def test_main_imports_rag_v2_api():
    source = Path("Edu_AI/api/Edu_AI/app/main.py").read_text(encoding="utf-8")
    assert "from rag_v2.api import router as rag_router, get_rag_system" in source
    assert "from new_rag.api import router as rag_router, get_rag_system" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_main_entrypoint.py -v`  
Expected: FAIL because `app/main.py` still imports `new_rag.api`

- [ ] **Step 3: Switch the main entrypoint import**

```python
# Edu_AI/api/Edu_AI/app/main.py
from rag_v2.api import router as rag_router, get_rag_system
```

Implementation notes:
- Do not change the mounted prefix or route registration order.
- Do not rewrite business logic in `app/main.py` during this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_main_entrypoint.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/main.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_main_entrypoint.py
git commit -m "feat: switch main app rag import to rag_v2"
```

### Task 4: Switch all backend callers from new_rag.api to rag_v2.api

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/courses.py`
- Modify: `Edu_AI/api/Edu_AI/app/deepsearch.py`
- Modify: `Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py`
- Modify: `Edu_AI/api/Edu_AI/app/blog_agent/engine.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_import_switch.py`

- [ ] **Step 1: Write the failing import switch test**

```python
from pathlib import Path


TARGETS = [
    "Edu_AI/api/Edu_AI/app/courses.py",
    "Edu_AI/api/Edu_AI/app/deepsearch.py",
    "Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py",
    "Edu_AI/api/Edu_AI/app/blog_agent/engine.py",
    "Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py",
    "Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py",
    "Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py",
    "Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py",
]


def test_backend_callers_no_longer_import_new_rag_api():
    for file_name in TARGETS:
        source = Path(file_name).read_text(encoding="utf-8")
        assert "from new_rag.api import" not in source
        assert "from rag_v2.api import" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_import_switch.py -v`  
Expected: FAIL because several files still import `new_rag.api`

- [ ] **Step 3: Switch all backend imports in one pass**

```python
# before
from new_rag.api import get_rag_system

# after
from rag_v2.api import get_rag_system
```

```python
# before
from new_rag.api import router as rag_router, get_rag_system

# after
from rag_v2.api import router as rag_router, get_rag_system
```

Implementation notes:
- Change imports only in this task.
- Do not rewrite existing call sites that use private `RAGSystem` members; the compatibility object must satisfy them unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_import_switch.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/courses.py Edu_AI/api/Edu_AI/app/deepsearch.py Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py Edu_AI/api/Edu_AI/app/blog_agent/engine.py Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_summary_provider.py Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_document_content_provider.py Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py Edu_AI/api/Edu_AI/app/chat/tools/search_tools.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_import_switch.py
git commit -m "refactor: switch backend rag callers to rag_v2"
```

### Task 5: Verify the compatibility surface and preserve rollback safety

**Files:**
- Modify: `Edu_AI/api/Edu_AI/rag_v2/README.md`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_object_compat.py`

- [ ] **Step 1: Write the failing compatibility object test**

```python
from rag_v2.api import get_rag_system


def test_rag_v2_system_exposes_legacy_runtime_members():
    rag_system = get_rag_system()
    assert hasattr(rag_system, "document_index")
    assert hasattr(rag_system, "document_processor")
    assert hasattr(rag_system, "vector_store")
    assert hasattr(rag_system, "_make_index_key")
    assert hasattr(rag_system, "_make_source_key")
    assert hasattr(rag_system, "_save_index")
    assert hasattr(rag_system, "_call_llm")
```

- [ ] **Step 2: Run test to verify it fails or reveals missing members**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_object_compat.py -v`  
Expected: FAIL if the wrapped object is not yet a true compatible runtime object

- [ ] **Step 3: Patch the compatibility layer and README**

```python
# Edu_AI/api/Edu_AI/rag_v2/api.py
_rag_system = None


def get_rag_system():
    global _rag_system
    if _rag_system is None:
        _rag_system = _get_runtime_rag_system()
    return _rag_system
```

```md
# Edu_AI/api/Edu_AI/rag_v2/README.md
- `rag_v2.api` is now the backend compatibility entrypoint.
- `new_rag` remains in the repository as a rollback reference during phase 1.
- Phase 1 intentionally does not expose `query_stream`, `import_image`, or `import_video` from the main backend router.
```

Implementation notes:
- The compatibility layer must return the actual runtime `RAGSystem`, not a reduced proxy.
- Keep `new_rag` code untouched so rollback remains a pure import-source revert.

- [ ] **Step 4: Run focused verification**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_runtime_import.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_api_compat.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_main_entrypoint.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_import_switch.py Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_object_compat.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/rag_v2/README.md Edu_AI/api/Edu_AI/tests/chat/test_rag_v2_object_compat.py
git commit -m "docs: document rag_v2 compat entrypoint and rollback"
```

## Self-Review

### Spec coverage

- Runtime package normalization: covered by Task 1
- Compatibility API surface: covered by Task 2
- Main router switch: covered by Task 3
- Full backend import switch: covered by Task 4
- Compatibility-object and rollback guarantees: covered by Task 5

No major spec requirement is currently uncovered.

### Placeholder scan

- No `TODO`
- No `TBD`
- No “implement later”
- No unspecified test commands

### Type consistency

- Public entrypoints stay aligned around `RAGSystem`, `get_rag_system`, and `rag_router`
- All plan tasks consistently use `rag_v2.api` as the new import source
- The runtime package name is consistently `rag_v2.rag_main`

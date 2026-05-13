from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


@dataclass
class EduAgentCapabilities:
    edu_agent_path: Path
    deepsearch_large_llm: Optional[Callable[..., Any]]
    get_crawler_service: Optional[Callable[..., Any]]
    ContentCleaner: Optional[type]
    get_storage_service: Optional[Callable[..., Any]]
    deepsearch_error: Optional[str] = None
    service_error: Optional[str] = None


def load_eduagent_capabilities(
    anchor_file: Optional[str | Path] = None,
    *,
    candidate_paths: Optional[Sequence[Path]] = None,
) -> EduAgentCapabilities:
    edu_agent_path = _resolve_eduagent_path(anchor_file, candidate_paths)
    _prepend_sys_path(edu_agent_path)

    deepsearch_large_llm, deepsearch_error = _load_deepsearch_callable(edu_agent_path)
    get_crawler_service, content_cleaner, get_storage_service, service_error = _load_services(
        edu_agent_path
    )

    return EduAgentCapabilities(
        edu_agent_path=edu_agent_path,
        deepsearch_large_llm=deepsearch_large_llm,
        get_crawler_service=get_crawler_service,
        ContentCleaner=content_cleaner,
        get_storage_service=get_storage_service,
        deepsearch_error=deepsearch_error,
        service_error=service_error,
    )


def _resolve_eduagent_path(
    anchor_file: Optional[str | Path],
    candidate_paths: Optional[Sequence[Path]],
) -> Path:
    if candidate_paths:
        paths = [Path(path) for path in candidate_paths]
    else:
        base_dir = Path(anchor_file or __file__).resolve().parent
        paths = [
            base_dir.parent.parent.parent.parent.parent / "EduAgent",
            base_dir.parent.parent.parent.parent / "EduAgent",
        ]
    return next((path for path in paths if path.exists()), paths[0])


def _prepend_sys_path(path: Path) -> None:
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def _load_deepsearch_callable(
    edu_agent_path: Path,
) -> tuple[Optional[Callable[..., Any]], Optional[str]]:
    deepsearch_path = edu_agent_path / "deepsearch.py"
    if not deepsearch_path.exists():
        return None, "EduAgent deepsearch.py not found"

    try:
        module = _load_module_from_path(deepsearch_path, "eduagent_deepsearch")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    deepsearch_large_llm = getattr(module, "deepsearch_large_llm", None)
    if deepsearch_large_llm is None:
        return None, "EduAgent deepsearch_large_llm not found"
    return deepsearch_large_llm, None


def _load_services(
    edu_agent_path: Path,
) -> tuple[Optional[Callable[..., Any]], Optional[type], Optional[Callable[..., Any]], Optional[str]]:
    services_path = edu_agent_path / "services"
    if not services_path.exists():
        return None, None, None, "EduAgent services directory not found"

    _prepend_sys_path(services_path)

    crawler_service = None
    content_cleaner = None
    storage_service = None
    errors: list[str] = []

    try:
        crawler_module = _load_module_from_path(
            services_path / "crawler_service.py",
            "eduagent_crawler_service",
        )
        crawler_service = getattr(crawler_module, "get_crawler_service", None)
        if crawler_service is None:
            errors.append("crawler_service.get_crawler_service not found")
    except Exception as exc:
        errors.append(f"crawler_service: {type(exc).__name__}: {exc}")

    try:
        cleaner_module = _load_module_from_path(
            services_path / "content_cleaner.py",
            "eduagent_content_cleaner",
        )
        content_cleaner = getattr(cleaner_module, "ContentCleaner", None)
        if content_cleaner is None:
            errors.append("content_cleaner.ContentCleaner not found")
    except Exception as exc:
        errors.append(f"content_cleaner: {type(exc).__name__}: {exc}")

    try:
        storage_module = _load_module_from_path(
            services_path / "storage_service.py",
            "eduagent_storage_service",
        )
        storage_service = getattr(storage_module, "get_storage_service", None)
        if storage_service is None:
            errors.append("storage_service.get_storage_service not found")
    except Exception as exc:
        errors.append(f"storage_service: {type(exc).__name__}: {exc}")

    return (
        crawler_service,
        content_cleaner,
        storage_service,
        "; ".join(errors) or None,
    )


def _load_module_from_path(file_path: Path, module_prefix: str) -> Any:
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    module_name = f"{module_prefix}_{hashlib.md5(str(file_path).encode('utf-8')).hexdigest()}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

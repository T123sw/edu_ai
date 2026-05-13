import sys
from pathlib import Path
import shutil
import uuid

sys.path.append(str(Path(__file__).resolve().parents[2]))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _purge_modules(*module_names: str) -> None:
    prefixes = tuple(f"{name}." for name in module_names)
    for name in list(sys.modules):
        if name in module_names or name.startswith(prefixes):
            sys.modules.pop(name, None)


def _make_temp_dir() -> Path:
    base_dir = Path(r"D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\.tmp")
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"deepsearch-loader-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    return temp_dir


def test_load_eduagent_capabilities_keeps_search_available_when_services_fail():
    from app.deepsearch_loader import load_eduagent_capabilities

    temp_dir = _make_temp_dir()
    eduagent_dir = temp_dir / "EduAgent"
    _write(
        eduagent_dir / "deepsearch.py",
        "def deepsearch_large_llm(query):\n"
        "    return {'links': [query]}\n",
    )

    original_sys_path = list(sys.path)
    _purge_modules("deepsearch", "services", "crawler_service", "content_cleaner", "storage_service")
    try:
        capabilities = load_eduagent_capabilities(candidate_paths=[eduagent_dir])
    finally:
        sys.path[:] = original_sys_path
        _purge_modules("deepsearch", "services", "crawler_service", "content_cleaner", "storage_service")
        shutil.rmtree(temp_dir, ignore_errors=True)

    assert capabilities.deepsearch_large_llm is not None
    assert capabilities.deepsearch_large_llm("计算思维") == {"links": ["计算思维"]}
    assert capabilities.get_crawler_service is None
    assert capabilities.ContentCleaner is None
    assert capabilities.get_storage_service is None
    assert capabilities.deepsearch_error is None
    assert capabilities.service_error is not None


def test_load_eduagent_capabilities_loads_services_when_present():
    from app.deepsearch_loader import load_eduagent_capabilities

    temp_dir = _make_temp_dir()
    eduagent_dir = temp_dir / "EduAgent"
    _write(
        eduagent_dir / "deepsearch.py",
        "def deepsearch_large_llm(query):\n"
        "    return {'links': [query, 'ok']}\n",
    )
    _write(eduagent_dir / "services" / "__init__.py", "")
    _write(
        eduagent_dir / "services" / "crawler_service.py",
        "def get_crawler_service():\n"
        "    return 'crawler-service'\n",
    )
    _write(
        eduagent_dir / "services" / "content_cleaner.py",
        "class ContentCleaner:\n"
        "    pass\n",
    )
    _write(
        eduagent_dir / "services" / "storage_service.py",
        "def get_storage_service():\n"
        "    return 'storage-service'\n",
    )

    original_sys_path = list(sys.path)
    _purge_modules("deepsearch", "services", "crawler_service", "content_cleaner", "storage_service")
    try:
        capabilities = load_eduagent_capabilities(candidate_paths=[eduagent_dir])
    finally:
        sys.path[:] = original_sys_path
        _purge_modules("deepsearch", "services", "crawler_service", "content_cleaner", "storage_service")
        shutil.rmtree(temp_dir, ignore_errors=True)

    assert capabilities.deepsearch_large_llm is not None
    assert capabilities.deepsearch_large_llm("topic") == {"links": ["topic", "ok"]}
    assert capabilities.get_crawler_service is not None
    assert capabilities.get_crawler_service() == "crawler-service"
    assert capabilities.ContentCleaner is not None
    assert capabilities.ContentCleaner.__name__ == "ContentCleaner"
    assert capabilities.get_storage_service is not None
    assert capabilities.get_storage_service() == "storage-service"
    assert capabilities.deepsearch_error is None
    assert capabilities.service_error is None

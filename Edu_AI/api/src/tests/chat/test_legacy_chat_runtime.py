import subprocess
import sys
from pathlib import Path

from app.chat.legacy.legacy_chat_runtime import LegacyChatRuntime


class DummyBackend:
    def __init__(self):
        self.chat_calls = []
        self.stream_calls = []
        self.health_calls = []

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return {"answer": "legacy"}

    def chat_stream_with_meta(self, **kwargs):
        self.stream_calls.append(kwargs)
        return {"conversation_id": "conv-1"}, [{"type": "done"}]

    def skill_health_check(self, meta):
        self.health_calls.append(meta)
        return {"score": 100.0}

    def get_report_engine(self):
        return {"engine": "report"}


def test_legacy_chat_runtime_delegates_all_public_calls():
    backend = DummyBackend()
    runtime = LegacyChatRuntime(backend=backend)

    assert runtime.chat(question="hello") == {"answer": "legacy"}
    assert runtime.chat_stream_with_meta(question="hello") == (
        {"conversation_id": "conv-1"},
        [{"type": "done"}],
    )
    assert runtime.skill_health_check({"x": 1}) == {"score": 100.0}
    assert runtime.get_report_engine() == {"engine": "report"}

    assert backend.chat_calls == [{"question": "hello"}]
    assert backend.stream_calls == [{"question": "hello"}]
    assert backend.health_calls == [{"x": 1}]


def test_legacy_chat_runtime_strips_new_runtime_only_kwargs_for_backend():
    backend = DummyBackend()
    runtime = LegacyChatRuntime(backend=backend)

    runtime.chat(
        question="hello",
        conversation_id="conv-1",
        allow_web=True,
        action_hint="research.lookup",
        artifact_id="artifact-1",
    )

    assert backend.chat_calls == [{"question": "hello", "conversation_id": "conv-1"}]


def test_legacy_chat_runtime_supports_lazy_backend_factory():
    created = []

    def factory():
        backend = DummyBackend()
        created.append(backend)
        return backend

    runtime = LegacyChatRuntime(backend_factory=factory)

    assert created == []
    assert runtime.chat(question="hello") == {"answer": "legacy"}
    assert len(created) == 1
    assert created[0].chat_calls == [{"question": "hello"}]


def test_legacy_chat_runtime_does_not_create_backend_until_first_use():
    created = []

    def factory():
        created.append("built")
        return DummyBackend()

    runtime = LegacyChatRuntime(backend_factory=factory)

    assert created == []
    assert runtime is not None
    assert created == []


def test_importing_legacy_chat_runtime_module_does_not_import_chat_service():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.legacy.legacy_chat_runtime; "
        "print('loaded=' + str('app.chat.service' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "loaded=False" in result.stdout


def test_importing_routes_module_does_not_import_chat_service():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "print('loaded=' + str('app.chat.service' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "loaded=False" in result.stdout


def test_importing_chat_package_does_not_import_chat_service():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat; "
        "print('loaded=' + str('app.chat.service' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "loaded=False" in result.stdout


def test_chat_package_still_exposes_router_without_importing_chat_service():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "from app.chat import router; "
        "print('router=' + str(router is not None)); "
        "print('loaded=' + str('app.chat.service' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "router=True" in result.stdout
    assert "loaded=False" in result.stdout


def test_importing_chat_package_does_not_import_routes_module():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat; "
        "print('routes=' + str('app.chat.routes' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "routes=False" in result.stdout


def test_root_app_package_still_exposes_fastapi_app_lazily():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "from app import app; "
        "print('has_app=' + str(app is not None)); "
        "print('routes=' + str('app.chat.routes' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "has_app=True" in result.stdout
    assert "routes=True" in result.stdout


def test_importing_route_chat_service_module_does_not_import_report_runtime():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.application.route_chat_service; "
        "print('report_runtime=' + str('app.chat.workflows.report.runtime' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "report_runtime=False" in result.stdout


def test_importing_routes_module_does_not_import_report_runtime():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "print('report_runtime=' + str('app.chat.workflows.report.runtime' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "report_runtime=False" in result.stdout


def test_importing_routes_module_does_not_build_route_service_runtime():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "targets = ["
        "'app.chat.application.route_chat_service',"
        "'app.chat.legacy.legacy_chat_runtime'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in targets))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "app.chat.application.route_chat_service=False" in result.stdout
    assert "app.chat.legacy.legacy_chat_runtime=False" in result.stdout


def test_importing_routes_module_does_not_import_response_builder():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "print('response_builder=' + str('app.chat.application.response_builder' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "response_builder=False" in result.stdout


def test_importing_routes_module_does_not_import_route_factories():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "targets = ["
        "'app.chat.application.route_feature_flags',"
        "'app.chat.application.route_service_factory'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in targets))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "app.chat.application.route_feature_flags=False" in result.stdout
    assert "app.chat.application.route_service_factory=False" in result.stdout


def test_importing_routes_module_does_not_import_legacy_router_stack():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.routes; "
        "legacy = ["
        "'app.chat.intent_router',"
        "'app.chat.response_planner',"
        "'app.chat.graph_state',"
        "'app.chat.resource_type_router',"
        "'app.chat.agents.supervisor_agent',"
        "'app.chat.agents.chat_agent',"
        "'app.chat.agents.research_agent'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in legacy))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    for name in [
        "app.chat.intent_router",
        "app.chat.response_planner",
        "app.chat.graph_state",
        "app.chat.resource_type_router",
        "app.chat.agents.supervisor_agent",
        "app.chat.agents.chat_agent",
        "app.chat.agents.research_agent",
    ]:
        assert f"{name}=False" in result.stdout


def test_importing_service_module_does_not_import_legacy_router_stack():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.service; "
        "legacy = ["
        "'app.chat.intent_router',"
        "'app.chat.response_planner',"
        "'app.chat.graph_state',"
        "'app.chat.resource_type_router',"
        "'app.chat.agents.supervisor_agent',"
        "'app.chat.agents.chat_agent',"
        "'app.chat.agents.research_agent'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in legacy))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    for name in [
        "app.chat.intent_router",
        "app.chat.response_planner",
        "app.chat.graph_state",
        "app.chat.resource_type_router",
        "app.chat.agents.supervisor_agent",
        "app.chat.agents.chat_agent",
        "app.chat.agents.research_agent",
    ]:
        assert f"{name}=False" in result.stdout


def test_importing_route_service_factory_module_does_not_import_runtime_modules():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.application.route_service_factory; "
        "targets = ["
        "'app.chat.application.route_chat_service',"
        "'app.chat.legacy.legacy_chat_runtime'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in targets))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "app.chat.application.route_chat_service=False" in result.stdout
    assert "app.chat.legacy.legacy_chat_runtime=False" in result.stdout


def test_importing_legacy_package_does_not_import_submodules():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import app.chat.legacy; "
        "targets = ["
        "'app.chat.legacy.compat_service',"
        "'app.chat.legacy.legacy_chat_runtime'"
        "]; "
        "print(';'.join(f'{name}={name in sys.modules}' for name in targets))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "app.chat.legacy.compat_service=False" in result.stdout
    assert "app.chat.legacy.legacy_chat_runtime=False" in result.stdout


def test_legacy_package_still_exposes_public_symbols_lazily():
    project_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "from app.chat.legacy import CompatChatService, LegacyChatRuntime; "
        "print('compat=' + str(CompatChatService is not None)); "
        "print('runtime=' + str(LegacyChatRuntime is not None))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "compat=True" in result.stdout
    assert "runtime=True" in result.stdout

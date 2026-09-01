import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module
from app.api import courses as courses_api
from app.services.course_access import CoursePrincipal
from app.services import course_service
from app.knowledge_graph_hours import KnowledgeGraphHourAllocationError
import modules.rag_v2.api as rag_api


class DummyManager:
    def __init__(self, graph=None):
        self.graph = graph
        self.saved = []

    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "Course 1"}
        return None

    def create_course_structure(self, course_id: str):
        return True

    def save_course_info(self, course_id: str, info: dict):
        return True

    def get_knowledge_graph(self, course_id: str):
        return self.graph

    def save_knowledge_graph(self, course_id: str, graph_data):
        self.saved.append({"course_id": course_id, "graph_data": graph_data})
        self.graph = graph_data
        return True


def make_client(manager: DummyManager):
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    app.dependency_overrides[courses_api.require_course_generate] = lambda: CoursePrincipal(
        course_id="course-1",
        user_id="teacher-a",
        system_role="teacher",
        course_role="editor",
    )
    return TestClient(app)


def graph():
    return {
        "id": "root",
        "label": "Course",
        "data": {"summary": "Root"},
        "children": [
            {"id": "leaf-a", "label": "A", "data": {"summary": "A"}, "children": []},
            {"id": "leaf-b", "label": "B", "data": {"summary": "B"}, "children": []},
        ],
    }


def test_allocate_hours_route_saves_and_returns_updated_graph(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    def fake_allocate(graph_data, total_hours, llm_call):
        assert total_hours == 2.5
        assert llm_call("prompt") == '{"allocations": []}'
        updated = {
            **graph_data,
            "data": {**graph_data["data"], "hours": 2.5},
            "children": [
                {**graph_data["children"][0], "data": {"summary": "A", "hours": 1.5}},
                {**graph_data["children"][1], "data": {"summary": "B", "hours": 1.0}},
            ],
        }
        return updated, {"total_hours": 2.5, "leaf_count": 2, "source": "llm", "normalized": False}

    monkeypatch.setattr(courses_api, "allocate_graph_hours_from_llm", fake_allocate)
    monkeypatch.setattr(course_service, "_call_knowledge_graph_hour_llm", lambda prompt: '{"allocations": []}')

    client = make_client(manager)
    response = client.post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]["data"]["hours"] == 2.5
    assert payload["allocation"]["leaf_count"] == 2
    assert manager.saved == [{"course_id": "course-1", "graph_data": payload["root"]}]


def test_allocate_hours_route_returns_404_for_missing_course(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/missing/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404


def test_allocate_hours_route_returns_404_for_missing_graph(monkeypatch):
    manager = DummyManager(None)
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404
    assert manager.saved == []


def test_allocate_hours_route_maps_validation_errors_to_400(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    def fail_validation(graph_data, total_hours, llm_call):
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative with at most one decimal place")

    monkeypatch.setattr(courses_api, "allocate_graph_hours_from_llm", fail_validation)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.25})

    assert response.status_code == 400
    assert "total_hours" in response.json()["detail"]
    assert manager.saved == []


def test_allocate_hours_route_does_not_save_when_llm_call_fails(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    def fail_llm(graph_data, total_hours, llm_call):
        raise RuntimeError("upstream model timeout")

    monkeypatch.setattr(courses_api, "allocate_graph_hours_from_llm", fail_llm)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 502
    assert "upstream model timeout" in response.json()["detail"]
    assert manager.saved == []


def test_call_knowledge_graph_hour_llm_ignores_proxy_env_for_model_request(monkeypatch):
    captured = {}

    class DummyRagSystem:
        def _call_llm(self, prompt, llm_config=None):
            captured["prompt"] = prompt
            captured["llm_config"] = llm_config
            captured["HTTP_PROXY"] = os.environ.get("HTTP_PROXY")
            captured["HTTPS_PROXY"] = os.environ.get("HTTPS_PROXY")
            captured["ALL_PROXY"] = os.environ.get("ALL_PROXY")
            captured["GIT_HTTP_PROXY"] = os.environ.get("GIT_HTTP_PROXY")
            return "ok"

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("GIT_HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setattr(rag_api, "get_rag_system", lambda: DummyRagSystem())
    monkeypatch.setattr(course_service.Config, "get_deep_model", staticmethod(lambda: {"model": "test-model"}))

    result = course_service._call_knowledge_graph_hour_llm("allocate these hours")

    assert result == "ok"
    assert captured["prompt"] == "allocate these hours"
    assert captured["llm_config"] == {"model": "test-model"}
    assert captured["HTTP_PROXY"] is None
    assert captured["HTTPS_PROXY"] is None
    assert captured["ALL_PROXY"] is None
    assert captured["GIT_HTTP_PROXY"] is None
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:9"
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert os.environ["ALL_PROXY"] == "http://127.0.0.1:9"
    assert os.environ["GIT_HTTP_PROXY"] == "http://127.0.0.1:9"

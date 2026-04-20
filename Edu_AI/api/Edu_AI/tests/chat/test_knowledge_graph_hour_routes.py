from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module
from app.knowledge_graph_hours import KnowledgeGraphHourAllocationError


class DummyManager:
    def __init__(self, graph=None):
        self.graph = graph
        self.saved = []

    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "Course 1"}
        return None

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
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

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

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fake_allocate)
    monkeypatch.setattr(courses_module, "_call_knowledge_graph_hour_llm", lambda prompt: '{"allocations": []}')

    client = make_client(manager)
    response = client.post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]["data"]["hours"] == 2.5
    assert payload["allocation"]["leaf_count"] == 2
    assert manager.saved == [{"course_id": "course-1", "graph_data": payload["root"]}]


def test_allocate_hours_route_returns_404_for_missing_course(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/missing/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404


def test_allocate_hours_route_returns_404_for_missing_graph(monkeypatch):
    manager = DummyManager(None)
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404
    assert manager.saved == []


def test_allocate_hours_route_maps_validation_errors_to_400(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    def fail_validation(graph_data, total_hours, llm_call):
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative with at most one decimal place")

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fail_validation)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.25})

    assert response.status_code == 400
    assert "total_hours" in response.json()["detail"]
    assert manager.saved == []


def test_allocate_hours_route_does_not_save_when_llm_call_fails(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    def fail_llm(graph_data, total_hours, llm_call):
        raise RuntimeError("upstream model timeout")

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fail_llm)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 502
    assert "upstream model timeout" in response.json()["detail"]
    assert manager.saved == []

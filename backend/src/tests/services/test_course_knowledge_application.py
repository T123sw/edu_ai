import copy
from types import SimpleNamespace

import pytest

from app.persistence.postgres_knowledge_repository import KnowledgeBuildRevisionConflict
from app.services.course_knowledge_application import CourseKnowledgeApplicationService


class FakeCourseStorage:
    def get_course_info(self, course_id):
        if course_id != "course-1":
            return None
        return {"name": "算法设计", "description": "本科课程"}


class FakeRepository:
    def __init__(self, *, graph=None, version=None):
        self.latest = {"version": version, "graph": graph} if version is not None else None
        self.build = None

    def get_latest_graph_version(self, course_id):
        assert course_id == "course-1"
        return copy.deepcopy(self.latest)

    def create_build_draft(self, *, course_id, triggered_by, plan):
        self.build = {
            "build_id": "kb-1",
            "library_id": course_id,
            "triggered_by": triggered_by,
            "status": "draft",
            "phase": "draft_config",
            "progress": 0,
            "revision": 1,
            "metrics": {},
            "quality_score": None,
            "error": None,
            **copy.deepcopy(plan),
        }
        return copy.deepcopy(self.build)

    def get_build(self, build_id):
        if not self.build or self.build["build_id"] != build_id:
            return None
        return copy.deepcopy(self.build)


def proposal_generator(course_id, build_id, *, expected_revision, requirements,
                       owner_user_id, repository):
    assert (course_id, build_id, expected_revision) == ("course-1", "kb-1", 1)
    assert owner_user_id == "teacher-1"
    repository.build.update(
        revision=2,
        phase="proposal_review",
        knowledge_proposal={
            "mode": "create",
            "summary": f"围绕{requirements or '课程目标'}生成三档方案",
            "options": [{"id": "brief"}, {"id": "standard"}, {"id": "complete"}],
        },
    )
    return copy.deepcopy(repository.build)


def make_service(repository, *, submitter=None):
    return CourseKnowledgeApplicationService(
        course_storage=FakeCourseStorage(),
        repository=repository,
        proposal_generator=proposal_generator,
        job_submitter=submitter,
    )


def test_plan_creates_draft_and_returns_review_projection():
    repository = FakeRepository()
    result = make_service(repository).plan(
        course_id="course-1",
        actor_user_id="teacher-1",
        requirements="适合 16 学时",
    )

    assert repository.build["course_snapshot"] == {
        "id": "course-1",
        "name": "算法设计",
        "description": "本科课程",
    }
    assert repository.build["baseline_graph_version"] is None
    assert result == {
        "build_id": "kb-1",
        "revision": 2,
        "status": "awaiting_review",
        "phase": "proposal_review",
        "progress": 0,
            "summary": "围绕适合 16 学时生成三档方案",
            "proposal": repository.build["knowledge_proposal"],
            "intent": None,
            "quality_score": None,
            "quality_status": None,
            "quality_checks": [],
            "error": None,
        "published_version": None,
    }


def test_plan_existing_build_requires_revision_and_preserves_baseline():
    graph = {"id": "root", "data": {"source_build_id": "kb-old"}}
    repository = FakeRepository(graph=graph, version=3)
    service = make_service(repository)
    draft = service.create_draft(course_id="course-1", actor_user_id="teacher-1")

    assert draft["baseline_graph_version"] == 3
    assert draft["baseline_graph"] == graph
    with pytest.raises(ValueError, match="revision"):
        service.plan(
            course_id="course-1",
            actor_user_id="teacher-1",
            requirements="只补习题",
            build_id="kb-1",
        )


def test_plan_propagates_revision_conflict():
    repository = FakeRepository()
    service = CourseKnowledgeApplicationService(
        course_storage=FakeCourseStorage(),
        repository=repository,
        proposal_generator=lambda *args, **kwargs: (_ for _ in ()).throw(
            KnowledgeBuildRevisionConflict("stale")
        ),
    )
    service.create_draft(course_id="course-1", actor_user_id="teacher-1")

    with pytest.raises(KnowledgeBuildRevisionConflict, match="stale"):
        service.plan(
            course_id="course-1",
            actor_user_id="teacher-1",
            requirements="更新方案",
            build_id="kb-1",
            expected_revision=1,
        )


def test_status_is_course_scoped_and_reports_published_version():
    repository = FakeRepository(
        graph={"id": "root", "data": {"source_build_id": "kb-1"}},
        version=4,
    )
    service = make_service(repository)
    service.create_draft(course_id="course-1", actor_user_id="teacher-1")
    repository.build.update(
        status="succeeded",
        phase="published",
        progress=100,
        quality_score=92.5,
        knowledge_proposal={"summary": "已完成"},
    )

    result = service.status(course_id="course-1", build_id="kb-1")
    assert result["published_version"] == 4
    assert result["quality_score"] == 92.5

    with pytest.raises(ValueError, match="不存在"):
        service.status(course_id="other-course", build_id="kb-1")


def test_retry_only_submits_failed_build_and_returns_job_projection():
    repository = FakeRepository()
    submitted = []

    class Job:
        def model_dump(self, **_kwargs):
            return {"job_id": "job-1", "status": "queued"}

    def submitter(**kwargs):
        submitted.append(kwargs)
        repository.build.update(status="queued", phase="retry_queued", progress=0, error=None)
        return Job()

    service = make_service(repository, submitter=submitter)
    service.create_draft(course_id="course-1", actor_user_id="teacher-1")
    repository.build.update(status="failed", error={"message": "network"})

    result = service.retry(
        course_id="course-1",
        actor_user_id="teacher-1",
        build_id="kb-1",
    )

    assert submitted == [{
        "course_id": "course-1",
        "owner_user_id": "teacher-1",
        "build_id": "kb-1",
        "retry": True,
    }]
    assert result["status"] == "queued"
    assert result["job"] == {"job_id": "job-1", "status": "queued"}

    repository.build["status"] = "running"
    with pytest.raises(ValueError, match="失败、阻塞或已取消"):
        service.retry(
            course_id="course-1",
            actor_user_id="teacher-1",
            build_id="kb-1",
        )


def test_http_draft_route_delegates_to_the_application_boundary(monkeypatch):
    from app.api import courses
    from app.schemas.course import CourseKnowledgeBuildDraftCreateRequest

    repository = FakeRepository()
    monkeypatch.setattr(courses._svc, "_get_manager", lambda: FakeCourseStorage())
    monkeypatch.setattr(
        courses, "get_postgres_knowledge_repository", lambda: repository
    )

    result = courses.create_knowledge_base_build_draft(
        "course-1",
        CourseKnowledgeBuildDraftCreateRequest(),
        SimpleNamespace(user_id="teacher-1"),
    )

    assert result["build_id"] == "kb-1"
    assert result["triggered_by"] == "teacher-1"
    assert result["course_snapshot"]["name"] == "算法设计"

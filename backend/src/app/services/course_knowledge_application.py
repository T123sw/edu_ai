"""Application boundary shared by HTTP routes and course-knowledge agent tools."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from typing import Any

from app.schemas.course import CourseKnowledgeBuildConfig
from app.services.course_knowledge_graph_incremental import (
    summarize_course_knowledge_graph,
)


def _generate_proposal(*args, **kwargs):
    from app.services.course_knowledge_proposals import generate_proposal

    return generate_proposal(*args, **kwargs)


def _submit_build_job(**kwargs):
    # Keep the durable worker import lazy: status and planning do not need the
    # task runtime (or its external integrations) during startup.
    from app.services.course_knowledge_plan_builder import (
        submit_course_knowledge_plan_build_job,
    )

    return submit_course_knowledge_plan_build_job(**kwargs)


class CourseKnowledgeApplicationService:
    """Own planning/status/retry use-cases without depending on FastAPI."""

    def __init__(
        self,
        *,
        course_storage=None,
        repository=None,
        proposal_generator: Callable[..., Mapping[str, Any]] | None = None,
        job_submitter: Callable[..., Any] | None = None,
    ) -> None:
        if course_storage is None:
            from core.course_storage import storage_manager

            course_storage = storage_manager
        if repository is None:
            from app.persistence.dependencies import get_postgres_knowledge_repository

            repository = get_postgres_knowledge_repository()
        self.course_storage = course_storage
        self.repository = repository
        self.proposal_generator = proposal_generator or _generate_proposal
        self.job_submitter = job_submitter or _submit_build_job

    def create_draft(
        self,
        *,
        course_id: str,
        actor_user_id: str,
        config: CourseKnowledgeBuildConfig | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        course = self.course_storage.get_course_info(course_id)
        if not course:
            raise ValueError("课程不存在")
        if config is None:
            normalized_config = CourseKnowledgeBuildConfig().model_dump(mode="json")
        elif isinstance(config, CourseKnowledgeBuildConfig):
            normalized_config = config.model_dump(mode="json")
        else:
            normalized_config = CourseKnowledgeBuildConfig.model_validate(
                dict(config)
            ).model_dump(mode="json")

        course_snapshot = dict(course)
        course_snapshot["id"] = course_id
        latest_graph = self.repository.get_latest_graph_version(course_id)
        baseline_graph = copy.deepcopy((latest_graph or {}).get("graph"))
        plan = {
            "course_id": course_id,
            "course_snapshot": course_snapshot,
            "config": normalized_config,
            "baseline_graph_version": (latest_graph or {}).get("version"),
            "baseline_graph": baseline_graph,
            "current_graph_summary": summarize_course_knowledge_graph(
                baseline_graph
            ),
            "textbooks": [],
            "graph_draft": None,
            "topics": [],
            "source_candidates": [],
            "warnings": [],
        }
        return self.repository.create_build_draft(
            course_id=course_id,
            triggered_by=actor_user_id,
            plan=plan,
        )

    def plan(
        self,
        *,
        course_id: str,
        actor_user_id: str,
        requirements: str = "",
        build_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if not build_id:
            build = self.create_draft(
                course_id=course_id,
                actor_user_id=actor_user_id,
            )
            build_id = str(build["build_id"])
            expected_revision = int(build["revision"])
        elif expected_revision is None:
            raise ValueError("修改方案需要指定当前 revision")

        build = self.proposal_generator(
            course_id,
            build_id,
            expected_revision=expected_revision,
            requirements=requirements,
            owner_user_id=actor_user_id,
            repository=self.repository,
        )
        return self._project(build, status_override="awaiting_review")

    def status(self, *, course_id: str, build_id: str) -> dict[str, Any]:
        build = self._require_build(course_id, build_id)
        return self._project(build)

    def retry(
        self,
        *,
        course_id: str,
        actor_user_id: str,
        build_id: str,
    ) -> dict[str, Any]:
        build = self._require_build(course_id, build_id)
        if build.get("status") not in {"blocked", "failed", "canceled"}:
            raise ValueError("只有失败、阻塞或已取消的构建可以重试")
        job = self.job_submitter(
            course_id=course_id,
            owner_user_id=actor_user_id,
            build_id=build_id,
            retry=True,
        )
        result = self._project(self._require_build(course_id, build_id))
        result["job"] = (
            job.model_dump(mode="json")
            if hasattr(job, "model_dump")
            else dict(job)
        )
        return result

    def _require_build(self, course_id: str, build_id: str) -> dict[str, Any]:
        build = self.repository.get_build(build_id)
        if not build or str(build.get("library_id") or "") != course_id:
            raise ValueError("课程知识库构建记录不存在")
        return build

    def _project(
        self,
        build: Mapping[str, Any],
        *,
        status_override: str | None = None,
    ) -> dict[str, Any]:
        proposal = copy.deepcopy(build.get("knowledge_proposal"))
        intent = copy.deepcopy(
            build.get("intent_contract") or (proposal or {}).get("intent")
        )
        metrics = dict(build.get("metrics") or {})
        summary = str((proposal or {}).get("summary") or "").strip()
        result = {
            "build_id": str(build.get("build_id") or ""),
            "revision": int(build.get("revision") or 0),
            "status": status_override or str(build.get("status") or "draft"),
            "phase": str(build.get("phase") or ""),
            "progress": int(build.get("progress") or 0),
            "summary": summary,
            "proposal": proposal,
            "intent": intent,
            "quality_score": build.get("quality_score"),
            "quality_status": metrics.get("quality_status"),
            "quality_checks": copy.deepcopy(metrics.get("checks") or []),
            "error": copy.deepcopy(build.get("error")),
            "published_version": None,
        }
        if build.get("status") == "succeeded":
            latest = self.repository.get_latest_graph_version(
                str(build.get("library_id") or "")
            )
            graph_data = dict(((latest or {}).get("graph") or {}).get("data") or {})
            if graph_data.get("source_build_id") == build.get("build_id"):
                result["published_version"] = (latest or {}).get("version")
        return result

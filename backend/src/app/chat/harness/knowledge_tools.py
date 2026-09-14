"""Course planning tools. Confirmation is exclusively a version-bound UI command."""
from urllib.parse import urlencode
from pydantic import BaseModel, ConfigDict, Field


class KnowledgePlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: str = Field(default="", max_length=4000)
    build_id: str | None = None
    revision: int | None = Field(default=None, ge=1)


class KnowledgeQueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    build_id: str | None = Field(default=None, min_length=1, max_length=200)


class KnowledgeRetryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    build_id: str = Field(min_length=1, max_length=200)


KNOWLEDGE_TOOLS = {
    "plan_course_knowledge": (
        KnowledgePlanArgs,
        "生成或修改当前课程知识库方案：新建返回三档大纲，补充返回缺口清单。不会确认、发布或入库。修改需原 build_id/revision。",
    ),
    "query_course_knowledge_build": (
        KnowledgeQueryArgs,
        "查询当前课程指定知识库构建的真实状态、阶段、进度、质量分与发布版本。",
    ),
    "retry_course_knowledge_build": (
        KnowledgeRetryArgs,
        "按教师明确要求，从稳定检查点重试当前课程中失败、阻塞或已取消且已确认的知识库构建。不会自动重试。",
    ),
}


class KnowledgeToolsMixin:
    _INFLIGHT_PLAN_KEY = "knowledge_plan_inflight"

    def _knowledge_principal(self):
        from app.api.course_dependencies import get_course_access_service

        return get_course_access_service().require(
            self.request.course_id,
            {"username": self.request.owner, "role": self.request.actor_role},
            "generate",
        )

    def _knowledge_application(self):
        application = getattr(self, "knowledge_application", None)
        if application is not None:
            return application
        from app.services.course_knowledge_application import (
            CourseKnowledgeApplicationService,
        )

        return CourseKnowledgeApplicationService(course_storage=self.course_storage)

    def _finish_knowledge_call(self, result):
        result = dict(result)
        result["review_url"] = "#knowledge?" + urlencode(
            {
                "course_id": self.request.course_id,
                "build_id": result["build_id"],
                "action": "build",
            }
        )
        self.session.data["knowledge_plan"] = {
            key: result.get(key)
            for key in (
                "build_id",
                "revision",
                "status",
                "phase",
                "progress",
                "summary",
                "intent",
                "quality_score",
                "quality_status",
                "quality_checks",
                "error",
                "published_version",
                "review_url",
            )
        }
        self.session.save()
        return result

    def plan_course_knowledge(self, args):
        principal = self._knowledge_principal()
        application = self._knowledge_application()
        build_id = args.build_id
        revision = args.revision

        # Proposal generation can involve several model calls.  If validation
        # asks the model to repair its output, the harness may invoke this tool
        # again in the same conversation. Persist the empty draft before the
        # expensive call so those retries never create orphan builds.
        if not build_id:
            inflight = self.session.data.get(self._INFLIGHT_PLAN_KEY) or {}
            if inflight.get("course_id") == self.request.course_id:
                candidate_id = str(inflight.get("build_id") or "")
                try:
                    candidate = application.status(
                        course_id=self.request.course_id,
                        build_id=candidate_id,
                    )
                except (KeyError, ValueError):
                    candidate = None
                if (
                    candidate
                    and candidate.get("status") == "draft"
                    and candidate.get("phase") == "draft_config"
                    and not candidate.get("proposal")
                ):
                    build_id = candidate_id
                    revision = int(candidate["revision"])
                else:
                    self.session.data.pop(self._INFLIGHT_PLAN_KEY, None)

            if not build_id:
                draft = application.create_draft(
                    course_id=self.request.course_id,
                    actor_user_id=principal.user_id,
                )
                build_id = str(draft["build_id"])
                revision = int(draft["revision"])
                self.session.data[self._INFLIGHT_PLAN_KEY] = {
                    "course_id": self.request.course_id,
                    "build_id": build_id,
                }
                self.session.save()

        result = application.plan(
            course_id=self.request.course_id,
            actor_user_id=principal.user_id,
            requirements=args.requirements,
            build_id=build_id,
            expected_revision=revision,
        )
        self.session.data.pop(self._INFLIGHT_PLAN_KEY, None)
        return self._finish_knowledge_call(result)

    def query_course_knowledge_build(self, args):
        self._knowledge_principal()
        build_id = args.build_id or (self.session.data.get("knowledge_plan") or {}).get("build_id")
        if not build_id:
            raise ValueError("请指定要查询的知识库 build_id")
        return self._finish_knowledge_call(
            self._knowledge_application().status(
                course_id=self.request.course_id,
                build_id=build_id,
            )
        )

    def retry_course_knowledge_build(self, args):
        principal = self._knowledge_principal()
        return self._finish_knowledge_call(
            self._knowledge_application().retry(
                course_id=self.request.course_id,
                actor_user_id=principal.user_id,
                build_id=args.build_id,
            )
        )

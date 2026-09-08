"""Course planning tools. Confirmation is exclusively a version-bound UI command."""
from urllib.parse import urlencode
from pydantic import BaseModel, ConfigDict, Field


class KnowledgePlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: str = Field(default="", max_length=4000)
    build_id: str | None = None
    revision: int | None = Field(default=None, ge=1)


KNOWLEDGE_TOOLS = {"plan_course_knowledge": (KnowledgePlanArgs,
    "生成或修改当前课程知识库方案：新建返回三档大纲，补充返回缺口清单。不会确认、发布或入库。修改需原 build_id/revision。")}


class KnowledgeToolsMixin:
    def plan_course_knowledge(self, args):
        from app.api.course_dependencies import get_course_access_service
        from app.api.courses import create_knowledge_base_build_draft
        from app.schemas.course import CourseKnowledgeBuildDraftCreateRequest
        from app.services.course_knowledge_proposals import generate_proposal
        principal = get_course_access_service().require(self.request.course_id,
            {"username": self.request.owner, "role": self.request.actor_role}, "generate")
        build_id, revision = args.build_id, args.revision
        if not build_id:
            build = create_knowledge_base_build_draft(self.request.course_id, CourseKnowledgeBuildDraftCreateRequest(), principal)
            build_id, revision = build["build_id"], build["revision"]
        if revision is None:
            raise ValueError("修改方案需要指定当前 revision")
        build = generate_proposal(self.request.course_id, build_id, expected_revision=revision,
                                  requirements=args.requirements, owner_user_id=self.request.owner)
        self.session.data["knowledge_plan"] = {"build_id": build_id, "revision": build["revision"], "summary": build["knowledge_proposal"]["summary"]}
        self.session.save()
        return {"build_id": build_id, "revision": build["revision"], "status": "awaiting_review",
                "proposal": build["knowledge_proposal"],
                "review_url": "#knowledge?" + urlencode({"course_id": self.request.course_id, "build_id": build_id, "action": "build"})}

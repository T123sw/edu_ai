"""Role-safe AI classroom curriculum catalog endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.course_dependencies import require_course_read
from app.api.resource_learning import get_resource_learning_service
from app.api.standard_resources import get_standard_resource_catalog_service
from app.classroom_catalog.service import ClassroomCatalogService
from app.schemas.classroom_catalog import ClassroomCatalogResponse
from app.services.course_access import CoursePrincipal


router = APIRouter(prefix="/api/courses/{course_id}", tags=["classroom-catalog"])


def get_classroom_catalog_service() -> ClassroomCatalogService:
    return ClassroomCatalogService(
        get_standard_resource_catalog_service(),
        get_resource_learning_service(),
    )


@router.get("/classroom-catalog", response_model=ClassroomCatalogResponse)
def get_classroom_catalog(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: ClassroomCatalogService = Depends(get_classroom_catalog_service),
) -> ClassroomCatalogResponse:
    mode = "manage" if principal.course_role in {"owner", "editor"} else "learn"
    return ClassroomCatalogResponse.model_validate(
        service.build(
            course_id=course_id,
            mode=mode,
            student_id=principal.user_id if mode == "learn" else None,
        )
    )

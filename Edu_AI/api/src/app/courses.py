"""Backward-compat re-exports — new code should import from app.api.courses directly."""

from __future__ import annotations

from fastapi import UploadFile

from app.api import courses as _api
from app.schemas.course import (
    AddRAGDocumentRequest,
    CourseInfo,
    KnowledgeBaseDocument,
    KnowledgeGraphData,
    KnowledgeGraphHourAllocationRequest,
    KnowledgeGraphHourAllocationResponse,
    PinMaterialRequest,
)

router = _api.router
get_current_user = _api.get_current_user

# route handlers for test compat (tests call these directly)
list_courses = _api.list_courses
get_course = _api.get_course
update_course = _api.update_course
create_course = _api.create_course
delete_course = _api.delete_course
get_course_materials = _api.get_course_materials
delete_course_material = _api.delete_course_material
pin_course_material = _api.pin_course_material
get_knowledge_base_documents = _api.get_knowledge_base_documents
upload_knowledge_base_document = _api.upload_knowledge_base_document
import_textbook_knowledge_graph = _api.import_textbook_knowledge_graph
add_rag_document_to_course_kb = _api.add_rag_document_to_course_kb
delete_knowledge_base_document = _api.delete_knowledge_base_document
get_knowledge_graph = _api.get_knowledge_graph
get_knowledge_graph_subtree = _api.get_knowledge_graph_subtree
allocate_knowledge_graph_hours = _api.allocate_knowledge_graph_hours
save_knowledge_graph = _api.save_knowledge_graph

"""Owner-scoped personal knowledge documents independent of course editing."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from app.services import knowledge_document_service as knowledge_lifecycle
from core.config import Config
from core.course_storage import CourseStorageManager


class PersonalKnowledgeError(RuntimeError):
    pass


class PersonalKnowledgeNotFound(PersonalKnowledgeError):
    pass


class PersonalKnowledgeValidationError(PersonalKnowledgeError):
    pass


class _OwnerKnowledgeManager(CourseStorageManager):
    def __init__(self, *, root_path: Path, owner_user_id: str) -> None:
        self._owner_dir = root_path / hashlib.sha256(
            owner_user_id.encode("utf-8")
        ).hexdigest()
        super().__init__(root_path=str(root_path / ".manager"))

    def get_course_dir(self, course_id: str) -> Path:  # noqa: ARG002
        return self._owner_dir

    def _recover_orphaned_knowledge_base_entries(
        self,
        course_id: str,  # noqa: ARG002
        entries: list[dict[str, Any]],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        # Course recovery deliberately treats ownerless files as shared course
        # documents. Personal libraries never use that fallback.
        return []


class PersonalKnowledgeService:
    def __init__(self, *, root_path: Path | str | None = None) -> None:
        self.root_path = Path(
            root_path or (Path(Config.STORAGE_ROOT) / "personal_knowledge")
        )
        self.root_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _owner(owner_user_id: str) -> str:
        owner = str(owner_user_id or "").strip()
        if not owner:
            raise PersonalKnowledgeValidationError("缺少个人知识库所有者")
        return owner

    @staticmethod
    def access_domain(owner_user_id: str) -> str:
        owner = PersonalKnowledgeService._owner(owner_user_id)
        return f"personal:{owner}"

    @staticmethod
    def _safe_display_name(filename: str) -> str:
        value = str(filename or "").strip()
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or re.match(r"^[A-Za-z]:", value)
            or "\x00" in value
        ):
            raise PersonalKnowledgeValidationError("文件名不合法")
        return value

    def manager_for(self, owner_user_id: str) -> CourseStorageManager:
        owner = self._owner(owner_user_id)
        return _OwnerKnowledgeManager(
            root_path=self.root_path,
            owner_user_id=owner,
        )

    def list_documents(self, *, owner_user_id: str) -> list[dict[str, Any]]:
        owner = self._owner(owner_user_id)
        manager = self.manager_for(owner)
        records = manager.get_knowledge_base_index(
            self.access_domain(owner),
            library_type="personal",
            owner_user_id=owner,
        )
        return sorted(
            (dict(item) for item in records),
            key=lambda item: str(
                item.get("updated_at") or item.get("uploaded_at") or ""
            ),
            reverse=True,
        )

    def create_document(
        self,
        *,
        owner_user_id: str,
        filename: str,
        file_data: bytes,
        course_context_id: str | None = None,
    ) -> dict[str, Any]:
        owner = self._owner(owner_user_id)
        display_name = self._safe_display_name(filename)
        manager = self.manager_for(owner)
        access_domain = self.access_domain(owner)
        physical_name = f"{uuid.uuid4().hex}-{display_name}"
        relative_path = manager.save_knowledge_base_file(
            access_domain,
            bytes(file_data),
            physical_name,
            scope_type="course",
            scope_id=None,
            library_type="personal",
            owner_user_id=owner,
        )
        if not relative_path:
            raise PersonalKnowledgeError("保存个人文档失败")
        normalized_relative_path = str(relative_path).replace("\\", "/")
        record = next(
            (
                item
                for item in manager.get_knowledge_base_index(access_domain)
                if str(item.get("path") or "").replace("\\", "/")
                == normalized_relative_path
            ),
            None,
        )
        if record is None:
            raise PersonalKnowledgeError("读取个人文档记录失败")
        document_id = str(record.get("id") or "")
        initialized = knowledge_lifecycle.initialize_document(
            manager,
            access_domain,
            document_id,
        )
        return knowledge_lifecycle.patch_document(
            manager,
            access_domain,
            document_id,
            filename=display_name,
            display_name=display_name,
            library_type="personal",
            owner_user_id=owner,
            course_context_id=(
                str(course_context_id or "").strip() or None
            ),
            uploaded_at=initialized.get("uploaded_at"),
        )

    def get_document(
        self,
        *,
        owner_user_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        owner = self._owner(owner_user_id)
        document = knowledge_lifecycle.get_document(
            self.manager_for(owner),
            self.access_domain(owner),
            str(document_id or "").strip(),
            owner_user_id=owner,
        )
        if document is None:
            raise PersonalKnowledgeNotFound("文档不存在或无权访问")
        return document

    def read_content(
        self,
        *,
        owner_user_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        owner = self._owner(owner_user_id)
        document = self.get_document(
            owner_user_id=owner,
            document_id=document_id,
        )
        manager = self.manager_for(owner)
        file_path = (
            manager.get_course_dir(self.access_domain(owner))
            / str(document.get("path") or "")
        ).resolve()
        owner_root = manager.get_course_dir(self.access_domain(owner)).resolve()
        try:
            file_path.relative_to(owner_root)
        except ValueError as exc:
            raise PersonalKnowledgeValidationError("文档路径不合法") from exc
        if not file_path.is_file():
            raise PersonalKnowledgeNotFound("文档正文不存在")
        if file_path.suffix.casefold() not in {
            ".md",
            ".markdown",
            ".txt",
            ".html",
            ".htm",
            ".json",
            ".csv",
            ".py",
        }:
            raise PersonalKnowledgeValidationError(
                "该文件类型暂不支持直接预览正文"
            )
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "document_id": str(document.get("id") or document_id),
            "file_path": str(document.get("id") or document_id),
            "file_name": str(document.get("filename") or file_path.name),
            "content": content,
            "chunks": (
                [
                    {
                        "id": 0,
                        "content": content,
                        "page": 1,
                        "metadata": {"document_id": document_id},
                    }
                ]
                if content.strip()
                else []
            ),
            "total_chunks": 1 if content.strip() else 0,
        }

    def rename_document(
        self,
        *,
        owner_user_id: str,
        document_id: str,
        name: str,
    ) -> dict[str, Any]:
        owner = self._owner(owner_user_id)
        self.get_document(owner_user_id=owner, document_id=document_id)
        display_name = self._safe_display_name(name)
        return knowledge_lifecycle.patch_document(
            self.manager_for(owner),
            self.access_domain(owner),
            document_id,
            filename=display_name,
            display_name=display_name,
        )

    def delete_document(
        self,
        *,
        owner_user_id: str,
        document_id: str,
        rag_system: Any | None = None,
    ) -> None:
        owner = self._owner(owner_user_id)
        manager = self.manager_for(owner)
        access_domain = self.access_domain(owner)
        document = self.get_document(
            owner_user_id=owner,
            document_id=document_id,
        )
        file_path = manager.get_file_path(
            access_domain,
            str(document.get("path") or ""),
        )
        if rag_system is not None and file_path.exists():
            rag_system.delete_document(str(file_path), owner=owner)
        if file_path.exists():
            file_path.unlink()
        records = manager.get_knowledge_base_index(access_domain)
        if not manager.save_knowledge_base_index(
            access_domain,
            [
                item
                for item in records
                if str(item.get("id") or "") != document_id
            ],
        ):
            raise PersonalKnowledgeError("删除个人文档记录失败")

    def submit_index(
        self,
        *,
        owner_user_id: str,
        document_id: str,
        rag_system: Any,
        force_reindex: bool = False,
    ) -> dict[str, Any]:
        owner = self._owner(owner_user_id)
        job = knowledge_lifecycle.submit_index_job(
            manager=self.manager_for(owner),
            rag_system=rag_system,
            course_id=self.access_domain(owner),
            document_id=document_id,
            owner_user_id=owner,
            force_reindex=force_reindex,
            storage_scope="personal",
        )
        return job.model_dump(mode="json")

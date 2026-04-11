"""
Course storage manager.

Handles:
- course metadata and course info
- knowledge base files and index
- generated teaching materials
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


COURSE_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "course_data"

TYPE_MAPPING = {
    "audio": "audio",
    "lesson_plan": "lesson_plans",
    "graph": "graphs",
    "report": "reports",
    "ppt": "ppts",
    "blog": "blogs",
    "quiz": "quizzes",
}

DIR_TO_TYPE = {value: key for key, value in TYPE_MAPPING.items()}


class CourseStorageManager:
    """Manage persisted course assets on disk."""

    def __init__(self, root_path: Optional[str] = None):
        if root_path:
            self.root_path = Path(root_path)
        else:
            env_path = os.getenv("COURSE_STORAGE_ROOT")
            self.root_path = Path(env_path) if env_path else COURSE_STORAGE_ROOT
        self.courses_dir = self.root_path / "courses"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.courses_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_json(self, file_path: Path, payload: Dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _material_dir(self, course_id: str, material_type: str) -> Path:
        return self.get_course_dir(course_id) / "generated_materials" / TYPE_MAPPING.get(material_type, "others")

    def _normalize_material_id(self, material_id: str) -> str:
        normalized = str(material_id or "").strip()
        if not normalized:
            return ""
        normalized = normalized.replace(":", "__")
        normalized = re.sub(r'[<>"/\\\\|?*]', "_", normalized)
        return normalized

    def _material_file(self, course_id: str, material_type: str, material_id: str) -> Path:
        safe_material_id = self._normalize_material_id(material_id)
        return self._material_dir(course_id, material_type) / f"{safe_material_id}.json"

    def _timestamp(self, value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:
            return 0.0

    def _sort_generated_materials(self, materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            materials,
            key=lambda item: (
                0 if item.get("is_pinned") else 1,
                -self._timestamp(item.get("pinned_at")),
                -self._timestamp(item.get("updated_at") or item.get("created_at")),
            ),
        )

    def get_course_dir(self, course_id: str) -> Path:
        return self.courses_dir / course_id

    def create_course_structure(self, course_id: str) -> Path:
        course_dir = self.get_course_dir(course_id)
        (course_dir / "knowledge_base" / "documents").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "audio").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "lesson_plans").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "graphs").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "reports").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "ppts").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "blogs").mkdir(parents=True, exist_ok=True)
        (course_dir / "generated_materials" / "quizzes").mkdir(parents=True, exist_ok=True)

        metadata = {
            "course_id": course_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.save_course_metadata(course_id, metadata)
        self.save_knowledge_base_index(course_id, [])
        return course_dir

    def save_course_info(self, course_id: str, course_info: Dict[str, Any]) -> bool:
        try:
            info_file = self.get_course_dir(course_id) / "course_info.json"
            self._write_json(info_file, course_info)
            metadata = self.get_course_metadata(course_id)
            metadata["updated_at"] = datetime.now().isoformat()
            self.save_course_metadata(course_id, metadata)
            return True
        except Exception as e:
            print(f"Error saving course info: {e}")
            return False

    def get_course_info(self, course_id: str) -> Optional[Dict[str, Any]]:
        try:
            info_file = self.get_course_dir(course_id) / "course_info.json"
            if not info_file.exists():
                return None
            return self._read_json(info_file)
        except Exception as e:
            print(f"Error loading course info: {e}")
            return None

    def save_course_metadata(self, course_id: str, metadata: Dict[str, Any]) -> bool:
        try:
            metadata_file = self.get_course_dir(course_id) / "metadata.json"
            self._write_json(metadata_file, metadata)
            return True
        except Exception as e:
            print(f"Error saving course metadata: {e}")
            return False

    def get_course_metadata(self, course_id: str) -> Dict[str, Any]:
        metadata_file = self.get_course_dir(course_id) / "metadata.json"
        metadata = self._read_json(metadata_file)
        if metadata:
            return metadata
        return {
            "course_id": course_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def save_knowledge_base_file(self, course_id: str, file_data: bytes, filename: str) -> Optional[str]:
        try:
            kb_documents_dir = self.get_course_dir(course_id) / "knowledge_base" / "documents"
            kb_documents_dir.mkdir(parents=True, exist_ok=True)

            file_path = kb_documents_dir / filename
            with open(file_path, "wb") as f:
                f.write(file_data)

            index = self.get_knowledge_base_index(course_id)
            file_info = {
                "id": f"doc-{datetime.now().timestamp()}",
                "filename": filename,
                "path": f"knowledge_base/documents/{filename}",
                "size": len(file_data),
                "uploaded_at": datetime.now().isoformat(),
            }
            index.append(file_info)
            self.save_knowledge_base_index(course_id, index)
            return str(file_path.relative_to(self.get_course_dir(course_id)))
        except Exception as e:
            print(f"Error saving knowledge base file: {e}")
            return None

    def get_knowledge_base_index(self, course_id: str) -> List[Dict[str, Any]]:
        index_file = self.get_course_dir(course_id) / "knowledge_base" / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_knowledge_base_index(self, course_id: str, index: List[Dict[str, Any]]) -> bool:
        try:
            index_file = self.get_course_dir(course_id) / "knowledge_base" / "index.json"
            index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving knowledge base index: {e}")
            return False

    def save_knowledge_graph(self, course_id: str, graph_data: Dict[str, Any]) -> bool:
        try:
            graph_file = self.get_course_dir(course_id) / "knowledge_graph.json"
            self._write_json(graph_file, graph_data)
            return True
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")
            return False

    def get_knowledge_graph(self, course_id: str) -> Optional[Dict[str, Any]]:
        try:
            graph_file = self.get_course_dir(course_id) / "knowledge_graph.json"
            if not graph_file.exists():
                return None
            return self._read_json(graph_file)
        except Exception as e:
            print(f"Error loading knowledge graph: {e}")
            return None

    def save_generated_material(
        self,
        course_id: str,
        material_type: str,
        material_id: str,
        material_data: Dict[str, Any],
        file_data: Optional[bytes] = None,
    ) -> bool:
        try:
            material_dir = self._material_dir(course_id, material_type)
            material_dir.mkdir(parents=True, exist_ok=True)

            material_file = self._material_file(course_id, material_type, material_id)
            existing_data = self._read_json(material_file) or {}
            next_data = dict(existing_data)
            next_data.update(material_data or {})
            next_data["material_type"] = material_type
            next_data["material_id"] = self._normalize_material_id(material_id)
            next_data["created_at"] = str(
                next_data.get("created_at") or existing_data.get("created_at") or datetime.now().isoformat()
            )
            next_data["updated_at"] = datetime.now().isoformat()
            next_data["is_pinned"] = bool(next_data.get("is_pinned", existing_data.get("is_pinned", False)))
            next_data["pinned_at"] = (
                str(next_data.get("pinned_at") or existing_data.get("pinned_at") or datetime.now().isoformat())
                if next_data["is_pinned"]
                else None
            )

            if file_data:
                file_ext = next_data.get("file_extension", ".txt")
                attachment_path = material_dir / f"{material_id}{file_ext}"
                with open(attachment_path, "wb") as f:
                    f.write(file_data)
                next_data["file_path"] = str(attachment_path.relative_to(self.get_course_dir(course_id)))

            self._write_json(material_file, next_data)
            return True
        except Exception as e:
            print(f"Error saving generated material: {e}")
            return False

    def get_generated_material(self, course_id: str, material_type: str, material_id: str) -> Optional[Dict[str, Any]]:
        try:
            material_file = self._material_file(course_id, material_type, material_id)
            if not material_file.exists():
                return None
            return self._read_json(material_file)
        except Exception as e:
            print(f"Error loading generated material: {e}")
            return None

    def list_generated_materials(self, course_id: str, material_type: Optional[str] = None) -> List[Dict[str, Any]]:
        materials: List[Dict[str, Any]] = []

        try:
            generated_materials_dir = self.get_course_dir(course_id) / "generated_materials"
            if not generated_materials_dir.exists():
                return []

            if material_type:
                type_dir = generated_materials_dir / TYPE_MAPPING.get(material_type, "others")
                type_dirs = [type_dir] if type_dir.exists() else []
            else:
                type_dirs = [type_dir for type_dir in generated_materials_dir.iterdir() if type_dir.is_dir()]

            for type_dir in type_dirs:
                derived_type = DIR_TO_TYPE.get(type_dir.name, material_type or "unknown")
                for json_file in type_dir.glob("*.json"):
                    material_data = self._read_json(json_file)
                    if not material_data:
                        continue
                    material_data["material_id"] = json_file.stem
                    material_data["material_type"] = material_data.get("material_type") or derived_type
                    material_data["is_pinned"] = bool(material_data.get("is_pinned", False))
                    materials.append(material_data)
        except Exception as e:
            print(f"Error listing generated materials: {e}")

        return self._sort_generated_materials(materials)

    def delete_generated_material(self, course_id: str, material_type: str, material_id: str) -> bool:
        try:
            material_file = self._material_file(course_id, material_type, material_id)
            stored = self._read_json(material_file) or {}
            if not material_file.exists():
                return False

            material_file.unlink()
            relative_file_path = stored.get("file_path")
            if relative_file_path:
                attachment_path = self.get_file_path(course_id, str(relative_file_path))
                if attachment_path.exists():
                    attachment_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting generated material: {e}")
            return False

    def pin_generated_material(self, course_id: str, material_type: str, material_id: str, is_pinned: bool = True) -> bool:
        try:
            material_file = self._material_file(course_id, material_type, material_id)
            material_data = self._read_json(material_file)
            if not material_data:
                return False

            material_data["is_pinned"] = bool(is_pinned)
            material_data["pinned_at"] = datetime.now().isoformat() if is_pinned else None
            material_data["updated_at"] = datetime.now().isoformat()
            self._write_json(material_file, material_data)
            return True
        except Exception as e:
            print(f"Error pinning generated material: {e}")
            return False

    def delete_course(self, course_id: str) -> bool:
        try:
            course_dir = self.get_course_dir(course_id)
            if course_dir.exists():
                shutil.rmtree(course_dir)
            return True
        except Exception as e:
            print(f"Error deleting course: {e}")
            return False

    def get_file_path(self, course_id: str, relative_path: str) -> Path:
        return self.get_course_dir(course_id) / relative_path

    def file_exists(self, course_id: str, relative_path: str) -> bool:
        return self.get_file_path(course_id, relative_path).exists()


storage_manager = CourseStorageManager()

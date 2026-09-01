"""Application rules for teacher and student standard-resource projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import (
    STANDARD_KINDS,
    LeafNode,
    extract_leaf_nodes,
    stable_material_id,
    standard_material_type,
)


GraphLookup = Callable[[str], dict[str, Any] | None]
MaterialList = Callable[[str], list[dict[str, Any]]]
VersionLookup = Callable[[str, str, str, int], dict[str, Any] | None]


@dataclass(slots=True)
class StandardResourceSlot:
    standard_kind: str
    material_type: str
    material_id: str
    review_status: str
    current_version: int | None
    approved_version: int | None
    resource: dict[str, Any] | None


@dataclass(slots=True)
class StandardResourceLeaf:
    leaf_id: str
    title: str
    chapter_id: str | None
    chapter_title: str | None
    path_titles: tuple[str, ...]
    slots: list[StandardResourceSlot]


@dataclass(slots=True)
class StandardResourceCatalog:
    course_id: str
    leaves: list[StandardResourceLeaf]


class StandardResourceService:
    def __init__(
        self,
        *,
        graph_lookup: GraphLookup,
        material_list: MaterialList,
        version_lookup: VersionLookup,
    ):
        self.graph_lookup = graph_lookup
        self.material_list = material_list
        self.version_lookup = version_lookup

    @staticmethod
    def _index_materials(materials: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        return {
            (str(item.get("material_type") or ""), str(item.get("material_id") or "")): item
            for item in materials
            if item.get("origin_type") == "standard"
        }

    def _teacher_slot(
        self,
        *,
        leaf: LeafNode,
        kind: str,
        material: dict[str, Any] | None,
    ) -> StandardResourceSlot:
        material_type = standard_material_type(kind)
        material_id = stable_material_id(leaf.leaf_id, kind)
        return StandardResourceSlot(
            standard_kind=kind,
            material_type=material_type,
            material_id=material_id,
            review_status=str(
                material.get("current_review_status") if material else "not_generated"
            ),
            current_version=int(material.get("version")) if material and material.get("version") else None,
            approved_version=(
                int(material["approved_version"])
                if material and material.get("approved_version") is not None
                else None
            ),
            resource=dict(material) if material else None,
        )

    def _student_slot(
        self,
        *,
        leaf: LeafNode,
        kind: str,
        material: dict[str, Any] | None,
        course_id: str,
    ) -> StandardResourceSlot | None:
        if not material or material.get("approved_version") is None:
            return None
        approved_version = int(material["approved_version"])
        material_type = standard_material_type(kind)
        material_id = stable_material_id(leaf.leaf_id, kind)
        version = self.version_lookup(
            course_id, material_type, material_id, approved_version
        )
        if version is None:
            return None
        resource = dict(material)
        resource.update(version)
        resource["version"] = approved_version
        resource["current_review_status"] = "approved"
        return StandardResourceSlot(
            standard_kind=kind,
            material_type=material_type,
            material_id=material_id,
            review_status="approved",
            current_version=approved_version,
            approved_version=approved_version,
            resource=resource,
        )

    def list_course_resources(
        self, *, course_id: str, can_manage: bool
    ) -> StandardResourceCatalog:
        leaves = extract_leaf_nodes(self.graph_lookup(course_id))
        materials = self._index_materials(self.material_list(course_id))
        result: list[StandardResourceLeaf] = []
        for leaf in leaves:
            slots: list[StandardResourceSlot] = []
            for kind in STANDARD_KINDS:
                material_type = standard_material_type(kind)
                material_id = stable_material_id(leaf.leaf_id, kind)
                material = materials.get((material_type, material_id))
                if can_manage:
                    slots.append(
                        self._teacher_slot(
                            leaf=leaf, kind=kind.value, material=material
                        )
                    )
                else:
                    slot = self._student_slot(
                        leaf=leaf,
                        kind=kind.value,
                        material=material,
                        course_id=course_id,
                    )
                    if slot is not None:
                        slots.append(slot)
            result.append(
                StandardResourceLeaf(
                    leaf_id=leaf.leaf_id,
                    title=leaf.title,
                    chapter_id=leaf.chapter_id,
                    chapter_title=leaf.chapter_title,
                    path_titles=leaf.path_titles,
                    slots=slots,
                )
            )
        return StandardResourceCatalog(course_id=course_id, leaves=result)

"""Read-only boundaries for committed manifests and existing learning rooms.

Loaders must enforce material-level authorization and return exact versions.
This adapter never publishes a manifest or changes a legacy course.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from .contracts import Actor, CourseView, ManifestRef, ObjectiveView, ResourceRef, ResourceView, TopicView


class CourseAccessDenied(Exception):
    pass


class ManifestUnavailable(Exception):
    pass


class ResourceVersionUnavailable(Exception):
    pass


class CourseReader:
    def __init__(self, *, authorize: Callable, load_manifest: Callable,
                 load_legacy: Callable, load_resource: Callable):
        self.authorize = authorize
        self.load_manifest = load_manifest
        self.load_legacy = load_legacy
        self.load_resource = load_resource

    def read(self, actor: Actor, course_id: str, manifest_ref: ManifestRef | None = None) -> CourseView:
        self.authorize(actor, course_id)
        manifest = self.load_manifest(actor, course_id, manifest_ref)
        if manifest is not None:
            if manifest.get('course_id') != course_id:
                raise ManifestUnavailable('manifest course mismatch')
            view = self._manifest(manifest)
            if manifest_ref is not None and view.manifest_ref != manifest_ref:
                raise ManifestUnavailable('requested manifest is not available')
            return view
        if manifest_ref is not None:
            raise ManifestUnavailable('requested manifest is not available')
        room = self.load_legacy(actor, course_id)
        if not room or room.get('id') != course_id:
            raise CourseAccessDenied()
        topics = []
        for chapter in room.get('chapters', []):
            resources = []
            for resource in chapter.get('resources', []):
                remote = resource.get('remote')
                if not resource.get('ready') or not remote:
                    continue
                # Missing old versions are not guessed to mean version 1.
                if remote.get('version') is None:
                    continue
                resources.append(ResourceView(title=resource.get('title', ''), resource_ref=ResourceRef(
                    course_id=remote['courseId'], material_type=remote['materialType'],
                    material_id=remote['materialId'], version=remote['version'])))
            topics.append(TopicView(topic_id=chapter['id'], title=chapter['title'], resources=resources))
        return CourseView(course_id=course_id, source='legacy', goal=room.get('goal', ''), topics=topics)

    def read_resource(self, actor: Actor, resource_ref: ResourceRef) -> Mapping:
        self.authorize(actor, resource_ref.course_id)
        value = self.load_resource(actor, resource_ref)
        if value is None or value.get('version') != resource_ref.version:
            raise ResourceVersionUnavailable(resource_ref)
        return value

    @staticmethod
    def _manifest(manifest: Mapping) -> CourseView:
        course_id = manifest['course_id']
        topics = []
        for node in sorted(manifest['nodes'], key=lambda n: n.get('order', 0)):
            resources = [ResourceView(
                resource_ref=ResourceRef(course_id=course_id, material_type=r['resource_type'],
                                         material_id=r['resource_id'], version=r['version']),
                title=r.get('title', r.get('purpose', '')), required=r.get('required'),
                order=r.get('order', 0), objective_ids=r.get('objective_ids', []))
                for r in sorted(node.get('resources', []), key=lambda r: r.get('order', 0))]
            # A malformed/partial requirement declaration must not imply completion.
            policy = 'explicit' if resources and all(r.required is not None for r in resources) else 'unknown'
            topics.append(TopicView(topic_id=node['node_id'], title=node['title'], resources=resources,
                completion_policy=policy,
                prerequisite_node_ids=node.get('prerequisite_node_ids', []),
                checks=node.get('checks', []), available_check_ids=[c['check_id'] for c in node.get('checks', [])],
                objectives=[ObjectiveView(**o) for o in node.get('objectives', [])],
                required_activity_ids=node.get('required_activity_ids', [])))
            # Manifest check references are not automatically runnable checks.
            # CheckService will resolve/authorize them before exposing actions (P4).
        return CourseView(course_id=course_id, source='manifest',
            manifest_ref=ManifestRef(manifest_id=manifest['manifest_id'], version=manifest['version']),
            route_version=manifest['route_version'], goal=manifest.get('goal', ''), topics=topics,
            completion_policy='explicit' if topics and all(t.completion_policy == 'explicit' for t in topics) else 'unknown')

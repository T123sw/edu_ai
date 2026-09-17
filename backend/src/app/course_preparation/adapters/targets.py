"""Current membership and exact committed versions authorize existing-course work."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User,CourseMembership,PreparedCoursePointer,PreparedManifestVersion,ConversationMessage
from ..tool_registry import digest
from ..manifest import CourseManifest
from ..lifecycle_repository import RevisionConflict


class TargetStore:
    def __init__(self, engine): self.engine=engine

    def read(self, owner, target):
        with Session(self.engine) as session:
            return self.read_in_session(session, owner, target)

    def read_in_session(self, session, owner, target):
        user=session.get(User,owner)
        if user is None or user.is_disabled or session.get(CourseMembership,(target.course_id,owner)) is None:
            raise PermissionError('TARGET_COURSE_UNAVAILABLE')
        pointer=session.get(PreparedCoursePointer,(owner,target.course_id))
        row=session.get(PreparedManifestVersion,(owner,target.course_id,pointer.version)) if pointer else None
        if row is None:
            # Only explicitly course-scoped committed manifests may seed a personal overlay.
            rows=session.scalars(select(PreparedManifestVersion).where(PreparedManifestVersion.course_id==target.course_id,
                PreparedManifestVersion.version==target.base_manifest_version)).all()
            row=next((r for r in rows if r.payload.get('space')=='course'),None)
        if row is None: raise PermissionError('TARGET_MANIFEST_UNAVAILABLE')
        if row.version!=target.base_manifest_version: raise RevisionConflict('MANIFEST_BASE_CHANGED')
        if digest(row.payload)!=row.content_digest: raise ValueError('TARGET_MANIFEST_CORRUPTED')
        manifest=CourseManifest.model_validate(row.payload).model_dump(mode='json')
        if target.base_route_version and target.base_route_version!=manifest['route_version']:
            raise RevisionConflict('ROUTE_BASE_CHANGED')
        node=next((n for n in manifest['nodes'] if n['node_id']==target.node_id),None)
        if target.node_id and node is None: raise PermissionError('TARGET_NODE_UNAVAILABLE')
        resource=next((r for r in node['resources'] if r['resource_id']==target.resource_id),None) if node else None
        if target.resource_id and (resource is None or resource['version']!=target.base_resource_version):
            raise RevisionConflict('RESOURCE_BASE_CHANGED')
        return {'manifest':manifest,'node':node,'resource':resource,'source_owner':row.owner_user_id}

    def authorize(self,owner,request):
        snapshot=self.read(owner,request.target)
        if request.learning_context:
            with Session(self.engine) as session:
                for ref in request.learning_context.evidence_refs:
                    message=session.get(ConversationMessage,ref)
                    if not request.origin or message is None or message.conversation_id!=request.origin.conversation_id:
                        raise PermissionError('LEARNING_EVIDENCE_UNAVAILABLE')
        return snapshot

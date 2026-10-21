"""Current membership and exact committed versions authorize existing-course work."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User,CourseMembership,PreparedCoursePointer,PreparedManifestVersion,ConversationMessage,MaterialVersion
from ..tool_registry import digest
from ..manifest import CourseManifest
from ..lifecycle_repository import RevisionConflict


class TargetStore:
    def __init__(self, engine): self.engine=engine

    def read(self, owner, target):
        with Session(self.engine) as session:
            return self.read_in_session(session, owner, target)

    def read_in_session(self, session, owner, target):
        user=session.get(User,owner,populate_existing=True)
        if user is None or user.is_disabled or session.get(CourseMembership,(target.course_id,owner),populate_existing=True) is None:
            raise PermissionError('TARGET_COURSE_UNAVAILABLE')
        pointer=session.get(PreparedCoursePointer,(owner,target.course_id),populate_existing=True)
        row=session.get(PreparedManifestVersion,(owner,target.course_id,pointer.version),populate_existing=True) if pointer else None
        if row is None:
            from ..publication import PreparedPublication
            row=PreparedPublication.current(session,target.course_id)
        if row is None:
            # Only explicitly course-scoped committed manifests may seed a personal overlay.
            rows=session.scalars(select(PreparedManifestVersion).where(PreparedManifestVersion.course_id==target.course_id,
                PreparedManifestVersion.version==target.base_manifest_version)).all()
            public=[r for r in rows if r.payload.get('space')=='course']
            if len(public)>1:raise PermissionError('AMBIGUOUS_PUBLIC_MANIFEST')
            row=public[0] if public else None
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
        resource_content=None
        if resource:
            material=session.scalar(select(MaterialVersion).where(MaterialVersion.course_id==target.course_id,
                MaterialVersion.material_type==resource['resource_type'],MaterialVersion.material_id==resource['resource_id'],MaterialVersion.version==resource['version']))
            if material is None or material.payload.get('content_hash')!=resource['content_sha256']:
                raise PermissionError('TARGET_RESOURCE_UNAVAILABLE')
            if material.payload.get('owner_user_id')!=user.username and material.payload.get('visibility')!='course':
                raise PermissionError('TARGET_RESOURCE_NOT_READABLE')
            resource_content=material.payload.get('preparation_artifact',{}).get('content',material.payload.get('content'))
        return {'manifest':manifest,'node':node,'resource':resource,'source_owner':row.owner_user_id,'resource_content':resource_content}

    def authorize(self,owner,request):
        with Session(self.engine) as session:
            return self.authorize_in_session(session,owner,request)

    def authorize_in_session(self,session,owner,request):
        snapshot=self.read_in_session(session,owner,request.target)
        if request.learning_context:
            for ref in request.learning_context.evidence_refs:
                message=session.get(ConversationMessage,ref,populate_existing=True)
                if not request.origin or message is None or message.conversation_id!=request.origin.conversation_id:
                    raise PermissionError('LEARNING_EVIDENCE_UNAVAILABLE')
        return snapshot

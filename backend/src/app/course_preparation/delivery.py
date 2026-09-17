"""The only success path: immutable manifest, materials, pointer and outbox atomically."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import (PreparedManifestVersion as Version,PreparedCoursePointer as Pointer,
    PreparationDeliveryEvent as Outbox,PreparationArtifact as Artifact,Course,CourseMembership,User)
from app.chat.memory.lifecycle import lock_epoch,MemoryLifecycle
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from .manifest import CourseManifest
from .quality import check_digest,RULE_VERSION,candidate_manifest
from .schemas import PreparationRequest
from .tool_registry import digest
from .lifecycle_repository import RevisionConflict
from .runner import DeliveryResult


class DeliveryService:
    def __init__(self,repository):
        self.repository,self.engine=repository,repository.engine
        self.materials=PostgresMaterialRepository(self.engine)

    def commit(self,context):
        with Session(self.engine) as session,session.begin():
            checkpoint=context.checkpoint
            lock_epoch(session,checkpoint['memory_subject'])
            MemoryLifecycle.validate_refs_in_session(session,checkpoint['memory_subject'],checkpoint['memory_refs'])
            prep,attempt,run,_=self.repository._locked(session,context)
            checkpoint=run.checkpoint
            quality=checkpoint.get('quality',{})
            if (attempt.stage!='commit' or quality.get('decision')!='pass' or quality.get('rule_version')!=RULE_VERSION
                    or quality.get('input_digest')!=check_digest(checkpoint)):
                raise ValueError('DELIVERY_CHECKS_STALE')
            manifest=CourseManifest.model_validate(checkpoint['candidate_manifest'])
            expected_manifest=candidate_manifest(context,checkpoint,PreparationRequest.model_validate(prep.request_payload))
            if manifest != expected_manifest: raise ValueError('MANIFEST_CANDIDATE_CHANGED')
            if manifest.created_by_preparation_id!=prep.preparation_id: raise ValueError('MANIFEST_TASK_MISMATCH')
            pointer=session.scalar(select(Pointer).where(Pointer.owner_user_id==prep.owner_user_id,Pointer.course_id==manifest.course_id).with_for_update())
            expected=prep.request_payload.get('target',{}).get('base_manifest_version',0) if prep.request_payload.get('target') else 0
            if (pointer.version if pointer else 0)!=expected or manifest.version!=expected+1:
                raise RevisionConflict('MANIFEST_BASE_CHANGED')
            actor=session.get(User,prep.owner_user_id)
            if actor is None or actor.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
            artifacts={r['artifact_id']:r for r in checkpoint['artifacts']}
            manifest_resources={r.resource_id:r for node in manifest.nodes for r in node.resources}
            for artifact_id,checked in artifacts.items():
                row=session.get(Artifact,artifact_id)
                if (row is None or row.owner_user_id!=prep.owner_user_id or row.status!='draft' or row.content is None
                        or row.spec_digest!=checked['spec_digest'] or digest(row.content)!=checked['content_digest']
                        or digest(checked['content'])!=row.content_digest):
                    raise ValueError('ARTIFACT_CHANGED_BEFORE_DELIVERY')
                resource=manifest_resources.get(row.resource_id)
                if resource is None or resource.content_sha256!=row.content_digest or resource.version!=row.resource_version:
                    raise ValueError('MANIFEST_RESOURCE_MISMATCH')
                # Revalidate the child's own dependency set, including late drafts.
                MemoryLifecycle.validate_refs_in_session(session,row.spec['memory_subject'],row.spec['memory_refs'])
            if set(manifest_resources)!={r['resource_id'] for r in artifacts.values()}:
                raise ValueError('MANIFEST_RESOURCE_SET_MISMATCH')
            course=session.get(Course,manifest.course_id)
            now=self.repository.clock()
            if course is None:
                if expected: raise RevisionConflict('TARGET_COURSE_MISSING')
                info={'id':manifest.course_id,'title':checkpoint['plan']['title'],'description':manifest.goal,
                    'created_by':actor.username,'created_at':now.isoformat(),'updated_at':now.isoformat(),
                    'self_learning':True,'prepared_course':True}
                course=Course(course_id=manifest.course_id,title=info['title'],description=manifest.goal,created_by=prep.owner_user_id,raw_payload=info)
                session.add(course); session.flush()
                session.add(CourseMembership(course_id=manifest.course_id,user_id=prep.owner_user_id,role='owner',added_by=prep.owner_user_id))
            elif session.get(CourseMembership,(manifest.course_id,prep.owner_user_id)) is None:
                raise PermissionError('COURSE_MEMBERSHIP_REVOKED')
            for checked in artifacts.values():
                artifact=checked['content']; spec=checked['spec']
                body=artifact['content']
                payload={'course_id':manifest.course_id,'material_type':checked['resource_type'],'material_id':checked['resource_id'],
                    'title':artifact['title'],'content':body,'generation_state':artifact['generation_state'],
                    'version':checked['resource_version'],'content_hash':checked['content_digest'],'visibility':'private','origin_type':'personal',
                    'owner_user_id':actor.username,'created_by':actor.username,'scope_type':'knowledge_point','scope_id':spec['node_id'],
                    'created_at':now.isoformat(),'updated_at':now.isoformat(),'learning_course_resource':True,
                    'preparation_id':prep.preparation_id,'preparation_artifact':artifact,'status':'ready'}
                if checked['resource_type']=='classroom': payload.update(body)
                if checked['resource_type']=='quiz': payload['questions']=body['questions']
                self.materials.upsert(payload,session=session)
                session.flush()
            payload=manifest.model_dump(mode='json')
            session.add(Version(owner_user_id=prep.owner_user_id,course_id=manifest.course_id,version=manifest.version,
                manifest_id=manifest.manifest_id,preparation_id=prep.preparation_id,payload=payload,content_digest=digest(payload)))
            if pointer is None:
                session.add(Pointer(owner_user_id=prep.owner_user_id,course_id=manifest.course_id,version=manifest.version))
            else: pointer.version=manifest.version
            result={'course_id':manifest.course_id,'manifest_id':manifest.manifest_id,'manifest_version':manifest.version,'course_ready':True}
            attempt.status='succeeded'; run.result_ref=result; run.lease_token=None; run.lease_until=None
            self.repository._event(session,prep,attempt,'succeeded',result)
            session.add(Outbox(event_id='delivery_'+prep.preparation_id,preparation_id=prep.preparation_id,owner_user_id=prep.owner_user_id,
                course_id=manifest.course_id,manifest_version=manifest.version,payload={'result_ref':result,'origin':prep.request_payload.get('origin')},delivered=False))
            return DeliveryResult(result)

    def read(self,owner,course_id,version=None):
        with Session(self.engine) as session:
            if session.get(CourseMembership,(course_id,owner)) is None: raise PermissionError('COURSE_UNAVAILABLE')
            pointer=session.get(Pointer,(owner,course_id))
            if pointer is None: return None
            row=session.get(Version,(owner,course_id,version or pointer.version))
            if row is None: raise LookupError('MANIFEST_VERSION_UNAVAILABLE')
            if digest(row.payload)!=row.content_digest: raise ValueError('MANIFEST_CORRUPTED')
            return CourseManifest.model_validate(row.payload).model_dump(mode='json')

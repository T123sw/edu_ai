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
            prep,attempt,run,budget=self.repository._locked(session,context)
            checkpoint=run.checkpoint
            from .retained_resources import read_retained
            if checkpoint.get('retained_node_ids') and read_retained(self.repository,context,checkpoint)!=checkpoint.get('retained_artifacts'):
                raise ValueError('RETAINED_RESOURCE_CHANGED_BEFORE_DELIVERY')
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
            base_snapshot=None
            if expected:
                from .adapters.targets import TargetStore
                base_snapshot=TargetStore(self.engine).read_in_session(session,prep.owner_user_id,PreparationRequest.model_validate(prep.request_payload).target)
                if checkpoint.get('target_snapshot')!=base_snapshot: raise RevisionConflict('TARGET_SNAPSHOT_CHANGED')
            if (pointer.version if pointer else base_snapshot['manifest']['version'] if base_snapshot else 0)!=expected or manifest.version!=expected+1:
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
            generated_ids={r['resource_id'] for r in artifacts.values()}
            retained={key:value for key,value in manifest_resources.items() if key not in generated_ids}
            base_resources={r['resource_id']:r for n in base_snapshot['manifest']['nodes'] for r in n['resources']} if base_snapshot else {}
            for key,resource in retained.items():
                if base_resources.get(key)!=resource.model_dump(mode='json'):
                    raise ValueError('UNVERIFIED_RETAINED_RESOURCE')
                from app.database.models import MaterialVersion
                stored=session.scalar(select(MaterialVersion).where(MaterialVersion.course_id==manifest.course_id,
                    MaterialVersion.material_type==resource.resource_type,MaterialVersion.material_id==key,MaterialVersion.version==resource.version))
                if stored is None or stored.payload.get('content_hash')!=resource.content_sha256:
                    raise ValueError('RETAINED_RESOURCE_UNAVAILABLE')
                if stored.payload.get('owner_user_id')!=actor.username and stored.payload.get('visibility')!='course':
                    raise PermissionError('RETAINED_RESOURCE_NOT_READABLE')
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
            # A crashed provider call has unknown usage. At terminal delivery
            # settle its full reservation instead of leaving invisible debt or
            # claiming zero cost. Late output cannot publish after success.
            from app.database.models import PreparationAction
            for action in session.scalars(select(PreparationAction).where(PreparationAction.preparation_id==prep.preparation_id,
                    PreparationAction.status=='pending',PreparationAction.kind=='model_completion')):
                self.repository._settle_action(session,prep,attempt,budget,action.action_id,
                    {'usage':'unknown','cost_basis':'reserved_upper_bound','reason':'prior_provider_completion_not_observed'},failed=True)
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

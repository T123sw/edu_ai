"""Private child generation facts, worker fencing and shared parent accounting."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import (PreparationArtifact as Artifact, CoursePreparationRecord as Prep,
    CoursePreparationAttemptRecord as Attempt, PreparationBudget as Budget, PreparationAction as Action,
    PreparationExecution, CourseMembership, User)
from app.chat.memory.lifecycle import lock_epoch, MemoryLifecycle
from .schemas import PreparationRequest
from .generation_contracts import ResourceSpec
from .lifecycle_repository import ACTIVE, StaleLease, BudgetExceeded
from .repository import aware
from .tool_registry import digest
from .runtime_contracts import BudgetCost


class ArtifactStore:
    def __init__(self,repository): self.repository,self.engine=repository,repository.engine

    def create(self,context,action_id,spec):
        raw_spec=deepcopy(spec)
        spec=ResourceSpec.model_validate(spec)
        artifact_id='artifact_'+digest(action_id)[:32]
        with Session(self.engine) as session,session.begin():
            prep,_,_,_=self.repository._locked(session,context)
            user=session.get(User,prep.owner_user_id)
            if user is None or spec.memory_subject!=user.username: raise PermissionError('MEMORY_SUBJECT_NOT_OWNED')
            action=session.get(Action,action_id)
            if action is None or action.preparation_id!=prep.preparation_id: raise PermissionError('ACTION_NOT_OWNED')
            row=session.get(Artifact,artifact_id)
            if row:
                if row.spec_digest!=digest(raw_spec): raise ValueError('RESOURCE_SPEC_CHANGED')
                return self.view(row)
            row=Artifact(artifact_id=artifact_id,preparation_id=prep.preparation_id,action_id=action_id,
                owner_user_id=prep.owner_user_id,resource_id=spec.delivery_resource_id or 'resource_'+digest(action_id)[:32],resource_version=spec.delivery_resource_version,
                resource_type=spec.resource_type,spec=raw_spec,spec_digest=digest(raw_spec),
                status='pending',created_at=self.repository.clock())
            # Reuse only an exact specification and verified content from a
            # previously committed course still accessible to this owner.
            candidates=session.scalars(select(Artifact).where(Artifact.owner_user_id==prep.owner_user_id,
                Artifact.spec_digest==row.spec_digest,Artifact.status=='draft').order_by(Artifact.created_at.desc())).all()
            for cached in candidates:
                original=session.get(Prep,cached.preparation_id)
                execution=session.get(PreparationExecution,(original.preparation_id,original.current_attempt_no))
                result=execution.result_ref or {}
                if not result.get('course_ready') or session.get(CourseMembership,(result.get('course_id'),prep.owner_user_id)) is None: continue
                if cached.content is None or digest(cached.content)!=cached.content_digest: continue
                MemoryLifecycle.validate_refs_in_session(session,spec.memory_subject,spec.memory_refs)
                row.content=deepcopy(cached.content); row.content_digest=cached.content_digest; row.status='draft'
                break
            session.add(row); session.flush()
            return self.view(row)

    @staticmethod
    def view(row):
        return {'artifact_id':row.artifact_id,'preparation_id':row.preparation_id,'owner_user_id':row.owner_user_id,
            'resource_id':row.resource_id,'resource_version':row.resource_version,'resource_type':row.resource_type,
            'spec':row.spec,'spec_digest':row.spec_digest,'status':row.status,'content_digest':row.content_digest,
            'error_code':row.error_code,
            'failure_detail':(row.content or {}).get('_failure_detail')}

    def get(self,owner,artifact_id,*,content=False):
        with Session(self.engine) as session:
            row=session.get(Artifact,artifact_id)
            if row is None or row.owner_user_id!=owner: raise LookupError('ARTIFACT_UNAVAILABLE')
            result=self.view(row)
            if content: result['content']=row.content
            return result

    def _parent(self,session,row):
        # Fixed lock order, shared with preference changes and final delivery.
        watermark=lock_epoch(session,row.spec['memory_subject'])
        if row.spec.get('memory_epoch',watermark.epoch)!=watermark.epoch:
            from app.chat.memory.lifecycle import MemoryChanged
            raise MemoryChanged('MEMORY_EPOCH_CHANGED')
        MemoryLifecycle.validate_refs_in_session(session,row.spec['memory_subject'],row.spec['memory_refs'])
        prep=session.scalar(select(Prep).where(Prep.preparation_id==row.preparation_id).with_for_update().execution_options(populate_existing=True))
        attempt=session.get(Attempt,(prep.preparation_id,prep.current_attempt_no))
        budget=session.get(Budget,prep.preparation_id)
        if attempt.status not in ACTIVE: raise StaleLease('PARENT_NOT_ACTIVE')
        if aware(budget.deadline)<=self.repository.clock(): raise BudgetExceeded('DEADLINE_EXCEEDED')
        user=session.get(User,prep.owner_user_id)
        if user is None or user.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
        self.repository.authorizer.authorize(prep.owner_user_id,PreparationRequest.model_validate(prep.request_payload))
        return prep,attempt,budget

    def claim(self,owner,artifact_id):
        with Session(self.engine) as session,session.begin():
            row=session.get(Artifact,artifact_id)
            if row is None or row.owner_user_id!=owner: raise LookupError('ARTIFACT_UNAVAILABLE')
            _,attempt,_=self._parent(session,row)
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==artifact_id).with_for_update().execution_options(populate_existing=True))
            if row.status=='draft': return None
            if row.status=='running' and row.lease_until and aware(row.lease_until)>self.repository.clock(): return None
            if row.status=='failed': raise ValueError('RESOURCE_REQUIRES_NEW_SPEC_REVISION')
            row.lease_token=uuid4().hex; row.lease_until=self.repository.clock()+timedelta(seconds=180)
            row.status='running'
            return {**self.view(row),'lease_token':row.lease_token,'parent_attempt_no':attempt.attempt_no}

    def _locked(self,session,context):
        row=session.get(Artifact,context['artifact_id'])
        if row is None or row.owner_user_id!=context['owner_user_id']: raise StaleLease('ARTIFACT_UNAVAILABLE')
        parent=self._parent(session,row)
        if context.get('parent_attempt_no',parent[1].attempt_no)!=parent[1].attempt_no:
            raise StaleLease('PARENT_ATTEMPT_CHANGED')
        row=session.scalar(select(Artifact).where(Artifact.artifact_id==row.artifact_id).with_for_update().execution_options(populate_existing=True))
        if row.status!='running' or row.lease_token!=context['lease_token'] or aware(row.lease_until)<=self.repository.clock():
            raise StaleLease('STALE_ARTIFACT_LEASE')
        row.lease_until=self.repository.clock()+timedelta(seconds=180)
        return row,*parent

    def begin_action(self,context,key,kind,payload,cost):
        with Session(self.engine) as session,session.begin():
            _,prep,_,budget=self._locked(session,context)
            return self.repository._reserve_action(session,prep,budget,'child:'+context['artifact_id']+':'+key,kind,payload,cost)

    def finish_action(self,context,action_id,receipt,actual=None,*,failed=False):
        with Session(self.engine) as session,session.begin():
            # Accounting for an already-started provider request may finish after
            # cancellation. This settles cost only and cannot save a resource.
            prep=session.scalar(select(Prep).where(Prep.preparation_id==context['preparation_id']).with_for_update())
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==context['artifact_id']).with_for_update().execution_options(populate_existing=True))
            action=session.get(Action,action_id)
            if row is None or row.owner_user_id!=context['owner_user_id'] or row.lease_token!=context['lease_token']:
                raise StaleLease('STALE_ARTIFACT_LEASE')
            if action is None or not action.action_key.startswith('child:'+row.artifact_id+':'):
                raise PermissionError('ACTION_NOT_OWNED')
            attempt=session.get(Attempt,(prep.preparation_id,prep.current_attempt_no))
            budget=session.get(Budget,prep.preparation_id)
            return self.repository._settle_action(session,prep,attempt,budget,action_id,receipt,actual,failed=failed)

    def save(self,context,artifact):
        with Session(self.engine) as session,session.begin():
            row,_,_,_=self._locked(session,context)
            if '_review_candidate' in artifact: raise ValueError('UNREVIEWED_CANDIDATE')
            artifact=deepcopy(artifact)
            candidate=(row.content or {}).get('_review_candidate') or (row.content or {}).get('_generation_recovery') or {}
            if candidate.get('recovery_receipt'):
                artifact.setdefault('generation_state',{})['preparation_recovery']={
                    key:deepcopy(candidate[key]) for key in ('recovery_key','recovery_receipt','recovery_attempt','parent_attempt_no')}
            from .resource_alignment import validate_artifact
            validate_artifact({**self.view(row),'content':artifact,'content_digest':digest(artifact)})
            row.content=dict(artifact); row.content_digest=digest(artifact)
            row.error_code=None
            row.status='draft'; row.lease_token=None; row.lease_until=None
            return self.view(row)

    def fail(self,context,code):
        # Retain diagnostics even after parent cancellation; never publish a draft.
        with Session(self.engine) as session,session.begin():
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==context['artifact_id']).with_for_update().execution_options(populate_existing=True))
            if row and row.owner_user_id==context['owner_user_id'] and row.preparation_id==context['preparation_id'] and row.lease_token==context['lease_token'] and row.status=='running':
                from .generation_failures import FailureDetail,GenerationFailure
                detail=code.detail if isinstance(code,GenerationFailure) else FailureDetail.model_validate(code) if isinstance(code,(dict,FailureDetail)) else None
                if detail is not None:
                    if detail.artifact_id not in (None,row.artifact_id): raise ValueError('FAILURE_ARTIFACT_MISMATCH')
                    candidate=(row.content or {}).get('_review_candidate')
                    if candidate and detail.content_digest not in (None,candidate['content_digest']): raise ValueError('FAILURE_CONTENT_MISMATCH')
                    row.content={**(row.content or {}),'_failure_detail':detail.model_dump(mode='json')}
                    row.content_digest=digest(row.content)
                row.status='failed'; row.error_code=detail.code if detail else code; row.lease_token=None; row.lease_until=None

    def checkpoint_port(self, context):
        from .resource_checkpoint import ArtifactResourceCheckpoint
        return ArtifactResourceCheckpoint(self, context)

    def resume_review(self, context, artifact_id, *, recovery_key):
        """Idempotent recovery intent; B must enqueue/read back this exact job ID.

        Parent fencing plus the artifact lock serialize competing workers. The
        key comes from the durable repair checkpoint, never from model output.
        """
        from .generation_failures import recovery_scope
        from .resource_checkpoint import ArtifactResourceCheckpoint
        with Session(self.engine) as session, session.begin():
            row=session.get(Artifact,artifact_id)
            if row is None or row.owner_user_id!=context.owner_user_id or row.preparation_id!=context.preparation_id:
                raise PermissionError('ARTIFACT_UNAVAILABLE')
            self._parent(session,row)
            prep,attempt,_,_=self.repository._locked(session,context)
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==artifact_id).with_for_update().execution_options(populate_existing=True))
            envelope=deepcopy(row.content or {})
            completed=envelope.get('generation_state',{}).get('preparation_recovery',{})
            if row.status=='draft' and completed.get('recovery_key')==recovery_key:
                if completed.get('parent_attempt_no')!=attempt.attempt_no: raise ValueError('REVIEW_CANDIDATE_STALE')
                if digest(row.content)!=row.content_digest: raise ValueError('ARTIFACT_CONTENT_MISMATCH')
                return completed['recovery_receipt']
            candidate=envelope.get('_review_candidate')
            if candidate is not None:
                ArtifactResourceCheckpoint._validate(candidate,row,prep,attempt)
            else:
                detail=envelope.get('_failure_detail') or {}
                if detail.get('category')!='provider': raise ValueError('REVIEW_CANDIDATE_MISSING')
                candidate=envelope.setdefault('_generation_recovery',{
                    'parent_attempt_no':attempt.attempt_no,'spec_digest':row.spec_digest})
                if candidate['parent_attempt_no']!=attempt.attempt_no or candidate['spec_digest']!=digest(row.spec):
                    raise ValueError('REVIEW_CANDIDATE_STALE')
            if candidate.get('recovery_key')==recovery_key:
                return candidate['recovery_receipt']
            if row.status!='failed': raise ValueError('RESOURCE_NOT_FAILED')
            detail=envelope.get('_failure_detail')
            if not detail: raise ValueError('FAILURE_DETAIL_MISSING')
            scope=recovery_scope(detail,attempts=candidate.get('recovery_attempt',0))
            if scope not in ('review','provider'): raise ValueError('CONTENT_REQUIRES_NEW_REVISION')
            number=candidate.get('recovery_attempt',0)+1
            receipt={'artifact_id':artifact_id,'job_id':f'generate_{artifact_id}_recovery_{number}',
                     'recovery_attempt':number,'retry_scope':scope}
            candidate.update(recovery_attempt=number,recovery_scope=scope,recovery_key=recovery_key,recovery_receipt=receipt)
            row.content=envelope;row.content_digest=digest(envelope)
            row.status='pending';row.error_code=None;row.lease_token=None;row.lease_until=None
            return receipt

"""Private child generation facts, worker fencing and shared parent accounting."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import (PreparationArtifact as Artifact, CoursePreparationRecord as Prep,
    CoursePreparationAttemptRecord as Attempt, PreparationBudget as Budget, PreparationAction as Action)
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
        spec=ResourceSpec.model_validate(spec)
        artifact_id='artifact_'+digest(action_id)[:32]
        with Session(self.engine) as session,session.begin():
            prep,_,_,_=self.repository._locked(session,context)
            action=session.get(Action,action_id)
            if action is None or action.preparation_id!=prep.preparation_id: raise PermissionError('ACTION_NOT_OWNED')
            row=session.get(Artifact,artifact_id)
            if row:
                if row.spec_digest!=digest(spec.model_dump(mode='json')): raise ValueError('RESOURCE_SPEC_CHANGED')
                return self.view(row)
            row=Artifact(artifact_id=artifact_id,preparation_id=prep.preparation_id,action_id=action_id,
                owner_user_id=prep.owner_user_id,resource_id='resource_'+digest(action_id)[:32],resource_version=1,
                resource_type=spec.resource_type,spec=spec.model_dump(mode='json'),spec_digest=digest(spec.model_dump(mode='json')),
                status='pending',created_at=self.repository.clock())
            session.add(row); session.flush()
            return self.view(row)

    @staticmethod
    def view(row):
        return {'artifact_id':row.artifact_id,'preparation_id':row.preparation_id,'owner_user_id':row.owner_user_id,
            'resource_id':row.resource_id,'resource_version':row.resource_version,'resource_type':row.resource_type,
            'spec':row.spec,'spec_digest':row.spec_digest,'status':row.status,'content_digest':row.content_digest,
            'error_code':row.error_code}

    def get(self,owner,artifact_id,*,content=False):
        with Session(self.engine) as session:
            row=session.get(Artifact,artifact_id)
            if row is None or row.owner_user_id!=owner: raise LookupError('ARTIFACT_UNAVAILABLE')
            result=self.view(row)
            if content: result['content']=row.content
            return result

    def _parent(self,session,row):
        # Fixed lock order, shared with preference changes and final delivery.
        lock_epoch(session,row.spec['memory_subject'])
        MemoryLifecycle.validate_refs_in_session(session,row.spec['memory_subject'],row.spec['memory_refs'])
        prep=session.scalar(select(Prep).where(Prep.preparation_id==row.preparation_id).with_for_update().execution_options(populate_existing=True))
        attempt=session.get(Attempt,(prep.preparation_id,prep.current_attempt_no))
        budget=session.get(Budget,prep.preparation_id)
        if attempt.status not in ACTIVE: raise StaleLease('PARENT_NOT_ACTIVE')
        if aware(budget.deadline)<=self.repository.clock(): raise BudgetExceeded('DEADLINE_EXCEEDED')
        self.repository.authorizer.authorize(prep.owner_user_id,PreparationRequest.model_validate(prep.request_payload))
        return prep,attempt,budget

    def claim(self,owner,artifact_id):
        with Session(self.engine) as session,session.begin():
            row=session.get(Artifact,artifact_id)
            if row is None or row.owner_user_id!=owner: raise LookupError('ARTIFACT_UNAVAILABLE')
            self._parent(session,row)
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==artifact_id).with_for_update().execution_options(populate_existing=True))
            if row.status=='draft': return None
            if row.status=='running' and row.lease_until and aware(row.lease_until)>self.repository.clock(): return None
            if row.status=='failed': raise ValueError('RESOURCE_REQUIRES_NEW_SPEC_REVISION')
            row.lease_token=uuid4().hex; row.lease_until=self.repository.clock()+timedelta(seconds=180)
            row.status='running'
            return {**self.view(row),'lease_token':row.lease_token}

    def _locked(self,session,context):
        row=session.get(Artifact,context['artifact_id'])
        if row is None or row.owner_user_id!=context['owner_user_id']: raise StaleLease('ARTIFACT_UNAVAILABLE')
        parent=self._parent(session,row)
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
            _,prep,attempt,budget=self._locked(session,context)
            return self.repository._settle_action(session,prep,attempt,budget,action_id,receipt,actual,failed=failed)

    def save(self,context,artifact):
        with Session(self.engine) as session,session.begin():
            row,_,_,_=self._locked(session,context)
            row.content=dict(artifact); row.content_digest=digest(artifact)
            row.status='draft'; row.lease_token=None; row.lease_until=None
            return self.view(row)

    def fail(self,context,code):
        # Retain diagnostics even after parent cancellation; never publish a draft.
        with Session(self.engine) as session,session.begin():
            row=session.scalar(select(Artifact).where(Artifact.artifact_id==context['artifact_id']).with_for_update().execution_options(populate_existing=True))
            if row and row.lease_token==context['lease_token'] and row.status=='running':
                row.status='failed'; row.error_code=code; row.lease_token=None; row.lease_until=None

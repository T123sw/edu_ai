"""Course/user rollout keeps migrated storage authoritative during model rollback."""
import copy
import os
from sqlalchemy.orm import Session
from .migration_models import LearningRolloutScope

def scoped_enabled():
    return os.getenv('LEARNING_SCOPED_ROLLOUT','').lower() in {'true','1'}

def phase(learning,owner,course):
    if not scoped_enabled():
        return 5
    if not learning.session_repository:
        return 0
    with Session(learning.session_repository.engine) as db:
        row=db.get(LearningRolloutScope,(owner,course))
        return row.phase if row else 0

def bind(learning,owner,course):
    if not scoped_enabled() or getattr(learning,'_scope_bound',None)==(owner,course):
        return learning
    value=copy.copy(learning)
    value._scope_bound=(owner,course)
    current=phase(learning,owner,course)
    from .session_service import SessionService
    from .progress_service import for_learning_service
    from .turn_service import TurnService
    from .check_service import CheckService
    from .memory_adapter import MemoryAdapter
    from .summary_service import SummaryService
    value.sessions=SessionService(value,value.session_repository) if current>=1 and value.session_repository else None
    value.progress_service=for_learning_service(value,value.progress_repository) if current>=2 and value.progress_repository else None
    value.turns=TurnService(value,value.turn_repository) if current>=3 and value.turns else None
    value.checks=value.memory=value.summaries=value.preparations=None
    if current>=4 and learning.memory:
        engine=value.session_repository.engine
        value.checks=CheckService(value,engine)
        value.memory=MemoryAdapter(value,engine)
        value.summaries=SummaryService(value,engine,value.memory)
        value.progress_service.repository.evidence_reader=value.checks.evidence
    if current>=5 and learning.preparations:
        from app.course_preparation.production_service import ProductionService
        from .preparation_adapter import PreparationAdapter
        value.preparations=PreparationAdapter(value,ProductionService(value,value.session_repository.engine))
    return value

from contextlib import contextmanager
from fastapi import HTTPException

@contextmanager
def legacy_write(learning,owner,course,domain_phase):
    if not scoped_enabled():
        yield
        return
    # Same cross-process lock as activation. Do not hold it during model I/O.
    with learning.session_repository._write('learning-migration:'+owner+':'+course) as db:
        scope=db.get(LearningRolloutScope,(owner,course))
        if scope and scope.phase>=domain_phase:
            raise HTTPException(409,'此学习记录已切换到新版存储，请刷新后继续')
        yield

"""Task-local assumptions and summaries; never a long-term preference write API."""
from sqlalchemy.orm import Session
from .schemas import Contract, ShortText
from pydantic import Field
from .lifecycle_repository import RevisionConflict


class WorkingMemory(Contract):
    revision: int=Field(default=0,ge=0)
    assumptions: tuple[ShortText,...]=Field(default=())
    open_questions: tuple[ShortText,...]=Field(default=())
    decisions: tuple[ShortText,...]=Field(default=())


def update_working_memory(repository,context,patch,*,expected_revision):
    with Session(repository.engine) as session, session.begin():
        _,_,run,_=repository._locked(session,context)
        current=WorkingMemory.model_validate(run.checkpoint.get('working_memory',{}))
        if current.revision!=expected_revision: raise RevisionConflict('WORKING_MEMORY_CHANGED')
        if 'revision' in patch: raise ValueError('MODEL_CANNOT_SET_REVISION')
        updated=WorkingMemory.model_validate({**current.model_dump(),**patch})
        if updated==current: raise ValueError('EMPTY_WORKING_MEMORY_PATCH')
        updated=updated.model_copy(update={'revision':current.revision+1})
        run.checkpoint={**run.checkpoint,'working_memory':updated.model_dump(mode='json')}
        return updated


def structural_summary(checkpoint):
    # A failed optional summarizer falls back to these facts; never interpret a
    # narrative summary as a job receipt, permission, budget or learning outcome.
    return {key:checkpoint[key] for key in ('brief','research_summary','plan','node_evidence','working_memory') if key in checkpoint}
